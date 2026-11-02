import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

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
    MATCHER_BATCHING_VERSION,
    EvidenceMatcherOutput,
)
from careerops.domain.evidence_matching import EvidenceMatcherInput
from careerops.domain.users import UserAccount
from careerops.main import create_app
from careerops.repositories.analysis_results import AnalysisResultRepository
from careerops.repositories.analysis_runs import AnalysisRunRepository
from careerops.services.analysis_results import AnalysisResultService
from careerops.services.analysis_run_execution import AnalysisRunExecutionService
from tests.integration.test_analysis_runs_postgres import (
    AllowingRateLimiter,
    RecordingDispatcher,
)

REQUIREMENT_COUNT = 13


class CountingMatcher(FakeEvidenceMatcher):
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def match(self, matcher_input: EvidenceMatcherInput) -> EvidenceMatcherOutput:
        self.batch_sizes.append(len(matcher_input.requirements))
        return await super().match(matcher_input)


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_batched_analysis_stores_every_requirement_in_one_completion() -> None:
    settings = Settings()
    session_factory = create_session_factory(settings.database_url)
    user_id = uuid4()
    job_id = uuid4()
    parse_run_id = uuid4()
    requirement_ids = [uuid4() for _ in range(REQUIREMENT_COUNT)]
    now = datetime.now(UTC)

    async with session_factory() as setup_session:
        setup_session.add(
            User(id=user_id, email=f"batching-{uuid4()}@example.com", password_hash="x")
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
                prompt_version="parse-v3",
                attempt=1,
                started_at=now,
                finished_at=now,
            )
        )
        await setup_session.flush()
        for requirement_id in requirement_ids:
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
    matcher = CountingMatcher()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            submitted = await client.post(
                f"/api/v1/jobs/{job_id}/analysis-runs",
                headers={"Idempotency-Key": "batching-key"},
                json={"parse_run_id": str(parse_run_id)},
            )
            assert submitted.status_code == 202
            analysis_run_id = UUID(submitted.json()["id"])

            async with session_factory() as worker_session:
                assert await AnalysisRunExecutionService(
                    store=AnalysisRunRepository(worker_session),
                    results=AnalysisResultService(AnalysisResultRepository(worker_session)),
                    matcher=matcher,
                ).execute(analysis_run_id)

            completed = await client.get(
                f"/api/v1/jobs/{job_id}/analysis-runs/{analysis_run_id}"
            )

    body = completed.json()
    assert completed.status_code == 200
    assert body["status"] == "succeeded"
    assert MATCHER_BATCHING_VERSION in body["prompt_version"].split(":")
    assert matcher.batch_sizes == [6, 6, 1]
    assert sorted(match["requirement_id"] for match in body["matches"]) == sorted(
        str(requirement_id) for requirement_id in requirement_ids
    )
    assert all(match["quote_valid"] for match in body["matches"])

    async with session_factory() as check_session:
        stored = await check_session.scalar(
            select(func.count())
            .select_from(EvidenceMatch)
            .where(EvidenceMatch.analysis_run_id == analysis_run_id)
        )
    assert stored == REQUIREMENT_COUNT

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(delete(AnalysisRun).where(AnalysisRun.user_id == user_id))
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()
