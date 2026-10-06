import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.adapters.evidence_matcher_factory import GROQ_EVIDENCE_MATCHER_MODEL
from careerops.domain.analysis_runs import (
    ANALYSIS_PROMPT_VERSION,
    FAKE_ANALYSIS_MODEL_NAME,
    AnalysisDispatchSource,
    AnalysisRateLimitReservation,
    AnalysisRunCreationResult,
    AnalysisRunRecord,
    AnalysisRunStatus,
    fake_matcher_pipeline_version,
    matcher_model_name_from_pipeline,
    matcher_pipeline_version,
)
from careerops.domain.embeddings import (
    FAKE_EMBEDDING_SPACE,
    GEMINI_EMBEDDING_SPACE,
    EmbeddingSpace,
)
from careerops.domain.errors import (
    AnalysisRateLimitExceededError,
    AnalysisRunDispatchError,
    IdempotencyKeyConflictError,
    NoActiveExperiencesError,
    ParseRunNotReadyError,
)
from careerops.domain.experiences import ExperienceKind, ExperienceRecord
from careerops.domain.jobs import JobRecord, JobStatus
from careerops.domain.parse_runs import (
    JobRequirementRecord,
    ParseRunRecord,
    ParseRunStatus,
    RequirementCategory,
)
from careerops.services.analysis_runs import (
    AnalysisRunService,
    compute_analysis_input_fingerprint,
)


class JobReader:
    def __init__(self, job: JobRecord) -> None:
        self.job = job

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None:
        if self.job.user_id == user_id and self.job.id == job_id:
            return self.job
        return None


class ParseRunReader:
    def __init__(self, run: ParseRunRecord | None) -> None:
        self.run = run

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord | None:
        if (
            self.run is not None
            and self.run.user_id == user_id
            and self.run.job_id == job_id
            and self.run.id == parse_run_id
        ):
            return self.run
        return None


class ExperienceReader:
    def __init__(self, experiences: list[ExperienceRecord]) -> None:
        self.experiences = experiences

    async def list_experiences(self, user_id: UUID) -> list[ExperienceRecord]:
        return [experience for experience in self.experiences if experience.user_id == user_id]


class AnalysisRunStore:
    def __init__(self, existing: AnalysisRunRecord | None = None) -> None:
        self.existing = existing
        self.committed = False

    async def get_analysis_run_by_idempotency_key(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRunRecord | None:
        if (
            self.existing is not None
            and self.existing.user_id == user_id
            and self.existing.job_id == job_id
            and self.existing.idempotency_key == idempotency_key
        ):
            return self.existing
        return None

    async def get_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        analysis_run_id: UUID,
    ) -> AnalysisRunRecord | None:
        if (
            self.existing is not None
            and self.existing.user_id == user_id
            and self.existing.job_id == job_id
            and self.existing.id == analysis_run_id
        ):
            return self.existing
        return None

    async def create_or_get_queued_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run: ParseRunRecord,
        idempotency_key: str,
        input_fingerprint: str,
        prompt_version: str,
    ) -> AnalysisRunCreationResult:
        self.existing = make_analysis_run(
            user_id=user_id,
            job_id=job_id,
            parse_run_id=parse_run.id,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
            prompt_version=prompt_version,
            model_name=matcher_model_name_from_pipeline(prompt_version),
        )
        return AnalysisRunCreationResult(run=self.existing, created=True)

    async def commit(self) -> None:
        self.committed = True


class ConcurrentLoserStore(AnalysisRunStore):
    def __init__(self, concurrent_run: AnalysisRunRecord) -> None:
        super().__init__()
        self.concurrent_run = concurrent_run

    async def create_or_get_queued_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run: ParseRunRecord,
        idempotency_key: str,
        input_fingerprint: str,
        prompt_version: str,
    ) -> AnalysisRunCreationResult:
        return AnalysisRunCreationResult(run=self.concurrent_run, created=False)


class FailingCreateStore(AnalysisRunStore):
    async def create_or_get_queued_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run: ParseRunRecord,
        idempotency_key: str,
        input_fingerprint: str,
        prompt_version: str,
    ) -> AnalysisRunCreationResult:
        raise RuntimeError("database write failed")


class Dispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.ids: list[UUID] = []
        self.correlations: list[tuple[str, AnalysisDispatchSource]] = []

    async def dispatch(
        self,
        analysis_run_id: UUID,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
    ) -> None:
        if self.fail:
            raise AnalysisRunDispatchError()
        self.ids.append(analysis_run_id)
        self.correlations.append((request_id, dispatch_source))


class RateLimiter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.reserved_user_ids: list[UUID] = []
        self.released: list[tuple[UUID, AnalysisRateLimitReservation]] = []

    async def reserve(self, user_id: UUID) -> AnalysisRateLimitReservation:
        if self.error is not None:
            raise self.error
        self.reserved_user_ids.append(user_id)
        return AnalysisRateLimitReservation(token=f"reservation-{len(self.reserved_user_ids)}")

    async def release(
        self,
        user_id: UUID,
        reservation: AnalysisRateLimitReservation,
    ) -> None:
        self.released.append((user_id, reservation))


@pytest.mark.asyncio
async def test_submit_analysis_run_commits_queued_run_then_dispatches(
    caplog: pytest.LogCaptureFixture,
) -> None:
    job, parse_run, experience = make_inputs()
    store = AnalysisRunStore()
    dispatcher = Dispatcher()
    service = build_service(job, parse_run, [experience], store, dispatcher)

    with caplog.at_level(logging.INFO):
        run = await service.submit_analysis_run(
            job.user_id,
            job.id,
            parse_run.id,
            "analysis-key",
            "request-1",
        )

    assert run.status is AnalysisRunStatus.QUEUED
    assert run.input_fingerprint == compute_analysis_input_fingerprint(parse_run, (experience,))
    assert store.committed
    assert dispatcher.ids == [run.id]
    assert dispatcher.correlations == [("request-1", AnalysisDispatchSource.SUBMISSION)]
    accepted = next(
        record for record in caplog.records if record.getMessage() == "analysis_run_accepted"
    )
    assert accepted.request_id == "request-1"
    assert accepted.run_id == str(run.id)
    assert accepted.attempt == 1
    assert accepted.outcome == "created"


@pytest.mark.asyncio
async def test_idempotent_replay_does_not_reserve_another_rate_limit_slot() -> None:
    job, parse_run, experience = make_inputs()
    existing = make_analysis_run(
        user_id=job.user_id,
        job_id=job.id,
        parse_run_id=parse_run.id,
        idempotency_key="analysis-key",
        input_fingerprint=compute_analysis_input_fingerprint(parse_run, (experience,)),
    )
    limiter = RateLimiter()
    service = build_service(
        job,
        parse_run,
        [experience],
        AnalysisRunStore(existing),
        Dispatcher(),
        rate_limiter=limiter,
    )

    replayed = await service.submit_analysis_run(
        job.user_id,
        job.id,
        parse_run.id,
        "analysis-key",
    )

    assert replayed.id == existing.id
    assert limiter.reserved_user_ids == []
    assert limiter.released == []


@pytest.mark.asyncio
async def test_concurrent_idempotency_loser_releases_its_rate_limit_slot() -> None:
    job, parse_run, experience = make_inputs()
    existing = make_analysis_run(
        user_id=job.user_id,
        job_id=job.id,
        parse_run_id=parse_run.id,
        idempotency_key="analysis-key",
        input_fingerprint=compute_analysis_input_fingerprint(parse_run, (experience,)),
    )
    limiter = RateLimiter()
    dispatcher = Dispatcher()
    service = build_service(
        job,
        parse_run,
        [experience],
        ConcurrentLoserStore(existing),
        dispatcher,
        rate_limiter=limiter,
    )

    run = await service.submit_analysis_run(
        job.user_id,
        job.id,
        parse_run.id,
        "analysis-key",
    )

    assert run.id == existing.id
    assert len(limiter.reserved_user_ids) == 1
    assert len(limiter.released) == 1
    assert dispatcher.ids == [existing.id]


@pytest.mark.asyncio
async def test_rate_limit_rejection_creates_no_run_and_dispatches_nothing() -> None:
    job, parse_run, experience = make_inputs()
    store = AnalysisRunStore()
    dispatcher = Dispatcher()
    service = build_service(
        job,
        parse_run,
        [experience],
        store,
        dispatcher,
        rate_limiter=RateLimiter(AnalysisRateLimitExceededError(60)),
    )

    with pytest.raises(AnalysisRateLimitExceededError):
        await service.submit_analysis_run(
            job.user_id,
            job.id,
            parse_run.id,
            "analysis-key",
        )

    assert store.existing is None
    assert not store.committed
    assert dispatcher.ids == []


@pytest.mark.asyncio
async def test_repository_creation_failure_releases_reservation() -> None:
    job, parse_run, experience = make_inputs()
    store = FailingCreateStore()
    limiter = RateLimiter()
    dispatcher = Dispatcher()
    service = build_service(
        job,
        parse_run,
        [experience],
        store,
        dispatcher,
        rate_limiter=limiter,
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        await service.submit_analysis_run(
            job.user_id,
            job.id,
            parse_run.id,
            "analysis-key",
        )

    assert not store.committed
    assert dispatcher.ids == []
    assert len(limiter.released) == 1


@pytest.mark.asyncio
async def test_analysis_run_binds_configured_retrieval_space() -> None:
    job, parse_run, experience = make_inputs()
    store = AnalysisRunStore()
    service = build_service(
        job,
        parse_run,
        [experience],
        store,
        Dispatcher(),
        retrieval_space=GEMINI_EMBEDDING_SPACE,
    )

    run = await service.submit_analysis_run(job.user_id, job.id, parse_run.id, "gemini-space")

    assert run.prompt_version == fake_matcher_pipeline_version(GEMINI_EMBEDDING_SPACE)


@pytest.mark.asyncio
async def test_analysis_run_binds_configured_matcher_model() -> None:
    job, parse_run, experience = make_inputs()
    service = build_service(
        job,
        parse_run,
        [experience],
        AnalysisRunStore(),
        Dispatcher(),
        matcher_model_name=GROQ_EVIDENCE_MATCHER_MODEL,
    )

    run = await service.submit_analysis_run(job.user_id, job.id, parse_run.id, "groq")

    assert run.model_name == GROQ_EVIDENCE_MATCHER_MODEL
    assert run.prompt_version == matcher_pipeline_version(
        FAKE_EMBEDDING_SPACE,
        GROQ_EVIDENCE_MATCHER_MODEL,
    )


@pytest.mark.asyncio
async def test_submit_analysis_run_rejects_parse_run_that_is_not_succeeded() -> None:
    job, parse_run, experience = make_inputs(parse_status=ParseRunStatus.QUEUED)
    service = build_service(job, parse_run, [experience], AnalysisRunStore(), Dispatcher())

    with pytest.raises(ParseRunNotReadyError):
        await service.submit_analysis_run(job.user_id, job.id, parse_run.id, "analysis-key")


@pytest.mark.asyncio
async def test_submit_analysis_run_requires_active_experience() -> None:
    job, parse_run, _ = make_inputs()
    service = build_service(job, parse_run, [], AnalysisRunStore(), Dispatcher())

    with pytest.raises(NoActiveExperiencesError):
        await service.submit_analysis_run(job.user_id, job.id, parse_run.id, "analysis-key")


@pytest.mark.asyncio
async def test_dispatch_failure_keeps_committed_queued_run() -> None:
    job, parse_run, experience = make_inputs()
    store = AnalysisRunStore()
    limiter = RateLimiter()
    service = build_service(
        job,
        parse_run,
        [experience],
        store,
        Dispatcher(fail=True),
        rate_limiter=limiter,
    )

    with pytest.raises(AnalysisRunDispatchError):
        await service.submit_analysis_run(job.user_id, job.id, parse_run.id, "analysis-key")

    assert store.existing is not None
    assert store.existing.status is AnalysisRunStatus.QUEUED
    assert store.committed
    assert limiter.released == []


@pytest.mark.asyncio
async def test_idempotency_key_cannot_be_reused_after_experience_changes() -> None:
    job, parse_run, experience = make_inputs()
    existing = make_analysis_run(
        user_id=job.user_id,
        job_id=job.id,
        parse_run_id=parse_run.id,
        idempotency_key="analysis-key",
        input_fingerprint="f" * 64,
    )
    service = build_service(
        job,
        parse_run,
        [experience],
        AnalysisRunStore(existing),
        Dispatcher(),
    )

    with pytest.raises(IdempotencyKeyConflictError):
        await service.submit_analysis_run(job.user_id, job.id, parse_run.id, "analysis-key")


def build_service(
    job: JobRecord,
    parse_run: ParseRunRecord,
    experiences: list[ExperienceRecord],
    store: AnalysisRunStore,
    dispatcher: Dispatcher,
    retrieval_space: EmbeddingSpace = FAKE_EMBEDDING_SPACE,
    matcher_model_name: str = FAKE_ANALYSIS_MODEL_NAME,
    rate_limiter: RateLimiter | None = None,
) -> AnalysisRunService:
    return AnalysisRunService(
        JobReader(job),
        ParseRunReader(parse_run),
        ExperienceReader(experiences),
        store,
        dispatcher,
        rate_limiter or RateLimiter(),
        retrieval_space,
        matcher_model_name,
    )


def make_inputs(
    *,
    parse_status: ParseRunStatus = ParseRunStatus.SUCCEEDED,
) -> tuple[JobRecord, ParseRunRecord, ExperienceRecord]:
    now = datetime.now(UTC)
    user_id = uuid4()
    job_id = uuid4()
    parse_run_id = uuid4()
    job = JobRecord(
        id=job_id,
        user_id=user_id,
        company="Example",
        title="Backend Intern",
        raw_description="Python required.",
        description_hash="a" * 64,
        source_url=None,
        location=None,
        deadline=None,
        status=JobStatus.SAVED,
        version=1,
        created_at=now,
        updated_at=now,
    )
    requirement = JobRequirementRecord(
        id=uuid4(),
        job_id=job_id,
        parse_run_id=parse_run_id,
        category=RequirementCategory.MUST_HAVE,
        text="Python required.",
        skill_normalized="Python",
        source_span_start=0,
        source_span_end=16,
    )
    parse_run = ParseRunRecord(
        id=parse_run_id,
        user_id=user_id,
        job_id=job_id,
        status=parse_status,
        idempotency_key="parse-key",
        input_fingerprint="b" * 64,
        model_name="fake-parser",
        prompt_version="parse-v2",
        attempt=1,
        error_code=None,
        latency_ms=0,
        input_tokens=None,
        output_tokens=None,
        started_at=now,
        finished_at=now,
        created_at=now,
        requirements=(requirement,),
    )
    experience = ExperienceRecord(
        id=uuid4(),
        user_id=user_id,
        title="CareerOps",
        kind=ExperienceKind.PROJECT,
        description="Built Python APIs.",
        skills=("Python",),
        outcome=None,
        version=1,
        content_hash="c" * 64,
        created_at=now,
        updated_at=now,
    )
    return job, parse_run, experience


def make_analysis_run(
    *,
    user_id: UUID,
    job_id: UUID,
    parse_run_id: UUID,
    idempotency_key: str,
    input_fingerprint: str,
    prompt_version: str = ANALYSIS_PROMPT_VERSION,
    model_name: str = FAKE_ANALYSIS_MODEL_NAME,
) -> AnalysisRunRecord:
    now = datetime.now(UTC)
    return AnalysisRunRecord(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        parse_run_id=parse_run_id,
        status=AnalysisRunStatus.QUEUED,
        idempotency_key=idempotency_key,
        input_fingerprint=input_fingerprint,
        model_name=model_name,
        prompt_version=prompt_version,
        attempt=1,
        validation_failure_count=0,
        error_code=None,
        latency_ms=None,
        input_tokens=None,
        output_tokens=None,
        started_at=None,
        finished_at=None,
        created_at=now,
        matches=(),
    )
