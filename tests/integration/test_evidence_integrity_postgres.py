import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

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
from careerops.domain.evidence_matching import EvidenceVerdict, ValidatedEvidenceMatch
from careerops.repositories.analysis_results import AnalysisResultRepository
from careerops.services.analysis_results import AnalysisResultService

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_invalid_positive_evidence_rolls_back_run_completion() -> None:
    session_factory = create_session_factory(Settings().database_url)
    user_id = uuid4()
    job_id = uuid4()
    parse_run_id = uuid4()
    requirement_id = uuid4()
    analysis_run_id = uuid4()
    now = datetime.now(UTC)

    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"evidence-{uuid4()}@example.com",
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
                description="Built reliable APIs.",
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
                source_span_start=0,
                source_span_end=16,
            )
        )
        await setup_session.flush()
        setup_session.add(
            AnalysisRun(
                id=analysis_run_id,
                user_id=user_id,
                job_id=job_id,
                parse_run_id=parse_run_id,
                status="running",
                idempotency_key="analysis",
                input_fingerprint="d" * 64,
                model_name="fake",
                prompt_version="match-v1",
                attempt=1,
                started_at=now,
            )
        )
        await setup_session.commit()

    invalid_match = ValidatedEvidenceMatch(
        requirement_id=requirement_id,
        verdict=EvidenceVerdict.MATCHED,
        experience_id=None,
        experience_version=None,
        quote=None,
        quote_valid=False,
        confidence=0.9,
        validation_failed=False,
    )
    async with session_factory() as execution_session:
        with pytest.raises(IntegrityError):
            await AnalysisResultService(AnalysisResultRepository(execution_session)).complete(
                analysis_run_id,
                (invalid_match,),
                model_name="fake-matcher",
                latency_ms=1,
                input_tokens=None,
                output_tokens=None,
            )
        await execution_session.rollback()

    async with session_factory() as verification_session:
        run_status = await verification_session.scalar(
            select(AnalysisRun.status).where(AnalysisRun.id == analysis_run_id)
        )
        evidence_count = await verification_session.scalar(
            select(func.count()).select_from(EvidenceMatch).where(
                EvidenceMatch.analysis_run_id == analysis_run_id
            )
        )
        user = await verification_session.get(User, user_id)
        assert user is not None
        await verification_session.delete(user)
        await verification_session.commit()

    await session_factory.kw["bind"].dispose()

    assert run_status == "running"
    assert evidence_count == 0
