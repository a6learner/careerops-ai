import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from careerops.adapters.evidence_matcher_factory import GROQ_EVIDENCE_MATCHER_MODEL
from careerops.adapters.fake_evidence_matcher import FakeEvidenceMatcher
from careerops.api.analysis_runs import get_analysis_rate_limiter, get_analysis_run_dispatcher
from careerops.api.dependencies import get_current_user
from careerops.core.config import Settings
from careerops.db.models import (
    AnalysisRun,
    EvidenceMatch,
    Experience,
    Job,
    JobRequirement,
    ParseRun,
    User,
)
from careerops.db.session import create_session_factory
from careerops.domain.analysis_runs import (
    ANALYSIS_PROMPT_VERSION,
    AnalysisDispatchSource,
    AnalysisRateLimitReservation,
    AnalysisRunErrorCode,
    AnalysisRunStatus,
    matcher_pipeline_version,
)
from careerops.domain.embeddings import FAKE_EMBEDDING_SPACE
from careerops.domain.parse_runs import ParseRunRecord, ParseRunStatus
from careerops.domain.users import UserAccount
from careerops.main import create_app
from careerops.repositories.analysis_results import AnalysisResultRepository
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import AnalysisRunExecutionService

pytestmark = pytest.mark.integration


class RecordingDispatcher:
    def __init__(self) -> None:
        self.ids: list[UUID] = []

    async def dispatch(
        self,
        analysis_run_id: UUID,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
    ) -> None:
        self.ids.append(analysis_run_id)


class AllowingRateLimiter:
    async def reserve(self, user_id: UUID) -> AnalysisRateLimitReservation:
        return AnalysisRateLimitReservation(token=str(uuid4()))

    async def release(
        self,
        user_id: UUID,
        reservation: AnalysisRateLimitReservation,
    ) -> None:
        return None


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_analysis_api_to_fake_worker_to_query() -> None:
    settings = Settings()
    session_factory = create_session_factory(settings.database_url)
    user_id = uuid4()
    job_id = uuid4()
    parse_run_id = uuid4()
    requirement_id = uuid4()
    now = datetime.now(UTC)

    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"analysis-{uuid4()}@example.com",
                password_hash="x",
            )
        )
        await setup_session.flush()
        setup_session.add(
            Job(
                id=job_id,
                user_id=user_id,
                company="Example",
                title="Backend Intern",
                raw_description="Python required.",
                description_hash="a" * 64,
                status="saved",
                version=1,
            )
        )
        setup_session.add(
            Experience(
                user_id=user_id,
                title="CareerOps AI",
                kind="project",
                description="Built reliable Python APIs.",
                skills=["Python"],
                version=1,
                content_hash="b" * 64,
            )
        )
        await setup_session.flush()
        setup_session.add(
            ParseRun(
                id=parse_run_id,
                user_id=user_id,
                job_id=job_id,
                status="succeeded",
                idempotency_key="parse",
                input_fingerprint="c" * 64,
                input_text="Python required.",
                model_name="fake",
                prompt_version="parse-v2",
                attempt=1,
                started_at=now,
                finished_at=now,
            )
        )
        await setup_session.flush()
        setup_session.add(
            JobRequirement(
                id=requirement_id,
                job_id=job_id,
                parse_run_id=parse_run_id,
                category="must_have",
                text="Python required.",
                skill_normalized="Python",
                source_span_start=0,
                source_span_end=16,
            )
        )
        await setup_session.commit()

    app = create_app()
    dispatcher = RecordingDispatcher()

    async def current_user() -> UserAccount:
        return UserAccount(id=user_id, email="student@example.com", created_at=now)

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_analysis_run_dispatcher] = lambda: dispatcher
    app.dependency_overrides[get_analysis_rate_limiter] = AllowingRateLimiter

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            submitted = await client.post(
                f"/api/v1/jobs/{job_id}/analysis-runs",
                headers={"Idempotency-Key": "analysis-key"},
                json={"parse_run_id": str(parse_run_id)},
            )
            assert submitted.status_code == 202
            assert submitted.json()["status"] == "queued"
            analysis_run_id = UUID(submitted.json()["id"])
            assert dispatcher.ids == [analysis_run_id]

            replayed = await client.post(
                f"/api/v1/jobs/{job_id}/analysis-runs",
                headers={"Idempotency-Key": "analysis-key"},
                json={"parse_run_id": str(parse_run_id)},
            )
            assert replayed.status_code == 202
            assert replayed.json()["id"] == str(analysis_run_id)
            assert dispatcher.ids == [analysis_run_id, analysis_run_id]

            async with session_factory() as worker_session:
                executed = await AnalysisRunExecutionService(
                    store=AnalysisRunRepository(worker_session),
                    results=AnalysisResultService(AnalysisResultRepository(worker_session)),
                    matcher=FakeEvidenceMatcher(),
                ).execute(analysis_run_id)
                assert executed

            completed = await client.get(
                f"/api/v1/jobs/{job_id}/analysis-runs/{analysis_run_id}"
            )

            async def other_user() -> UserAccount:
                return UserAccount(id=uuid4(), email="other@example.com", created_at=now)

            app.dependency_overrides[get_current_user] = other_user
            hidden = await client.get(
                f"/api/v1/jobs/{job_id}/analysis-runs/{analysis_run_id}"
            )

    body = completed.json()
    assert completed.status_code == 200
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "JOB_NOT_FOUND"
    assert body["status"] == "succeeded"
    assert body["model_name"] == "local-fake-evidence-matcher"
    assert body["validation_failure_count"] == 0
    assert body["matches"] == [
        {
            "id": body["matches"][0]["id"],
            "requirement_id": str(requirement_id),
            "experience_id": body["matches"][0]["experience_id"],
            "experience_version": 1,
            "verdict": "matched",
            "quote": "Python",
            "quote_valid": True,
            "confidence": None,
        }
    ]

    async with session_factory() as duplicate_session:
        duplicate_session.add(
            EvidenceMatch(
                analysis_run_id=analysis_run_id,
                requirement_id=requirement_id,
                verdict="missing",
                quote_valid=False,
            )
        )
        with pytest.raises(IntegrityError):
            await duplicate_session.commit()
        await duplicate_session.rollback()

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(
            delete(AnalysisRun).where(AnalysisRun.user_id == user_id)
        )
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_same_key_converges_and_different_key_creates_distinct_run() -> None:
    session_factory = create_session_factory(Settings().database_url)
    user_id = uuid4()
    job_id = uuid4()
    parse_run_id = uuid4()
    now = datetime.now(UTC)

    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"analysis-concurrency-{uuid4()}@example.com",
                password_hash="x",
            )
        )
        await setup_session.flush()
        setup_session.add(
            Job(
                id=job_id,
                user_id=user_id,
                company="Example",
                title="Backend Intern",
                raw_description="Python required.",
                description_hash="d" * 64,
                status="saved",
                version=1,
            )
        )
        await setup_session.flush()
        setup_session.add(
            ParseRun(
                id=parse_run_id,
                user_id=user_id,
                job_id=job_id,
                status="succeeded",
                idempotency_key="parse-concurrency",
                input_fingerprint="e" * 64,
                input_text="Python required.",
                model_name="fake",
                prompt_version="parse-v2",
                attempt=1,
                started_at=now,
                finished_at=now,
            )
        )
        await setup_session.commit()

    parse_run = ParseRunRecord(
        id=parse_run_id,
        user_id=user_id,
        job_id=job_id,
        status=ParseRunStatus.SUCCEEDED,
        idempotency_key="parse-concurrency",
        input_fingerprint="e" * 64,
        model_name="fake",
        prompt_version="parse-v2",
        attempt=1,
        error_code=None,
        latency_ms=0,
        input_tokens=None,
        output_tokens=None,
        started_at=now,
        finished_at=now,
        created_at=now,
        requirements=(),
    )

    async def create_run(
        idempotency_key: str,
        prompt_version: str = ANALYSIS_PROMPT_VERSION,
    ) -> tuple[UUID, bool]:
        async with session_factory() as session:
            repository = AnalysisRunRepository(session)
            creation = await repository.create_or_get_queued_analysis_run(
                user_id,
                job_id,
                parse_run,
                idempotency_key,
                "f" * 64,
                prompt_version,
            )
            if creation.created:
                await repository.commit()
            return creation.run.id, creation.created

    first, second = await asyncio.gather(create_run("analysis-a"), create_run("analysis-a"))

    assert first[0] == second[0]
    assert sorted([first[1], second[1]]) == [False, True]

    async with session_factory() as recovery_session:
        await recovery_session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.id == first[0])
            .values(status="running", started_at=now - timedelta(minutes=10))
        )
        await recovery_session.commit()

        repository = AnalysisRunRepository(recovery_session)
        requeued = await repository.requeue_stale_analysis_runs(now, 10)
        await repository.commit()
        recovered = await repository.get_analysis_run(user_id, job_id, first[0])

        current_work = await repository.claim_analysis_run(first[0])
        assert current_work is not None
        assert current_work.attempt == 2
        recovered_item = next(item for item in requeued if item.id == first[0])
        assert recovered_item.attempt == 2
        await repository.commit()

        assert not await repository.fail_analysis_run(
            first[0],
            1,
            "stale-worker",
            AnalysisRunErrorCode.MATCHER_FAILED,
            1,
        )
        assert not await AnalysisResultRepository(
            recovery_session
        ).complete_analysis_run(
            first[0],
            1,
            (),
            0,
            "stale-worker",
            1,
            None,
            None,
        )

    assert first[0] in {item.id for item in requeued}
    assert recovered is not None
    assert recovered.status is AnalysisRunStatus.QUEUED
    assert recovered.attempt == 2

    distinct = await create_run("analysis-b")

    assert distinct[0] != first[0]
    assert distinct[1]

    real_pipeline = matcher_pipeline_version(
        FAKE_EMBEDDING_SPACE,
        GROQ_EVIDENCE_MATCHER_MODEL,
    )
    real = await create_run("analysis-real", real_pipeline)
    async with session_factory() as session:
        real_run = await AnalysisRunRepository(session).get_analysis_run(
            user_id,
            job_id,
            real[0],
        )
    assert real_run is not None
    assert real_run.model_name == GROQ_EVIDENCE_MATCHER_MODEL
    assert real_run.prompt_version == real_pipeline

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(delete(AnalysisRun).where(AnalysisRun.user_id == user_id))
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()
