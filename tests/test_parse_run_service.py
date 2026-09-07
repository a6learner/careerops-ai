from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import (
    IdempotencyKeyConflictError,
    JobNotFoundError,
    ParseRunDispatchError,
    ParseRunNotFoundError,
)
from careerops.domain.jobs import JobRecord, JobStatus
from careerops.domain.parse_runs import (
    FAKE_PARSE_MODEL_NAME,
    PARSE_PROMPT_VERSION,
    ParseRunCreationResult,
    ParseRunRecord,
    ParseRunStatus,
)
from careerops.services.jobs import compute_description_hash
from careerops.services.parse_runs import (
    ParseRunService,
    compute_parse_input_fingerprint,
)


class InMemoryJobReader:
    def __init__(self, job: JobRecord | None) -> None:
        self.job = job

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None:
        if self.job is None or self.job.user_id != user_id or self.job.id != job_id:
            return None
        return self.job


class InMemoryParseRunStore:
    def __init__(self, existing: ParseRunRecord | None = None) -> None:
        self.existing = existing
        self.committed = False

    async def get_parse_run_by_idempotency_key(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord | None:
        if (
            self.existing is not None
            and self.existing.user_id == user_id
            and self.existing.job_id == job_id
            and self.existing.idempotency_key == idempotency_key
        ):
            return self.existing
        return None

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord | None:
        if (
            self.existing is not None
            and self.existing.user_id == user_id
            and self.existing.job_id == job_id
            and self.existing.id == parse_run_id
        ):
            return self.existing
        return None

    async def create_or_get_queued_parse_run(
        self,
        user_id: UUID,
        job: JobRecord,
        idempotency_key: str,
        input_fingerprint: str,
    ) -> ParseRunCreationResult:
        now = datetime.now(UTC)
        self.existing = ParseRunRecord(
            id=uuid4(),
            user_id=user_id,
            job_id=job.id,
            status=ParseRunStatus.QUEUED,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
            model_name=FAKE_PARSE_MODEL_NAME,
            prompt_version=PARSE_PROMPT_VERSION,
            attempt=1,
            error_code=None,
            latency_ms=None,
            input_tokens=None,
            output_tokens=None,
            started_at=None,
            finished_at=None,
            created_at=now,
            requirements=(),
        )
        return ParseRunCreationResult(run=self.existing, created=True)

    async def commit(self) -> None:
        self.committed = True


class RecordingDispatcher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.dispatched: list[UUID] = []

    async def dispatch(self, parse_run_id: UUID) -> None:
        if self.fail:
            raise ParseRunDispatchError()
        self.dispatched.append(parse_run_id)


def make_job(raw_description: str = "Python experience required. Preferred Redis.") -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        id=uuid4(),
        user_id=uuid4(),
        company="OpenAI",
        title="Backend Engineer Intern",
        raw_description=raw_description,
        description_hash=compute_description_hash(raw_description),
        source_url=None,
        location=None,
        deadline=None,
        status=JobStatus.SAVED,
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_submit_parse_run_creates_queued_run_commits_then_dispatches() -> None:
    job = make_job()
    store = InMemoryParseRunStore()
    dispatcher = RecordingDispatcher()
    service = ParseRunService(InMemoryJobReader(job), store, dispatcher)

    run = await service.submit_parse_run(job.user_id, job.id, "parse-key")

    assert run.status == ParseRunStatus.QUEUED
    assert run.input_fingerprint == compute_parse_input_fingerprint(job)
    assert run.model_name == FAKE_PARSE_MODEL_NAME
    assert run.requirements == ()
    assert store.committed
    assert dispatcher.dispatched == [run.id]


@pytest.mark.asyncio
async def test_submit_parse_run_reuses_existing_idempotency_key_without_commit() -> None:
    job = make_job()
    existing = ParseRunRecord(
        id=uuid4(),
        user_id=job.user_id,
        job_id=job.id,
        status=ParseRunStatus.SUCCEEDED,
        idempotency_key="parse-key",
        input_fingerprint=compute_parse_input_fingerprint(job),
        model_name=FAKE_PARSE_MODEL_NAME,
        prompt_version=PARSE_PROMPT_VERSION,
        attempt=1,
        error_code=None,
        latency_ms=0,
        input_tokens=None,
        output_tokens=None,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        requirements=(),
    )
    store = InMemoryParseRunStore(existing)
    dispatcher = RecordingDispatcher()
    service = ParseRunService(InMemoryJobReader(job), store, dispatcher)

    run = await service.submit_parse_run(job.user_id, job.id, "parse-key")

    assert run == existing
    assert not store.committed
    assert dispatcher.dispatched == []


@pytest.mark.asyncio
async def test_submit_parse_run_redispatches_existing_queued_run() -> None:
    job = make_job()
    existing = ParseRunRecord(
        id=uuid4(),
        user_id=job.user_id,
        job_id=job.id,
        status=ParseRunStatus.QUEUED,
        idempotency_key="parse-key",
        input_fingerprint=compute_parse_input_fingerprint(job),
        model_name=FAKE_PARSE_MODEL_NAME,
        prompt_version=PARSE_PROMPT_VERSION,
        attempt=1,
        error_code=None,
        latency_ms=None,
        input_tokens=None,
        output_tokens=None,
        started_at=None,
        finished_at=None,
        created_at=datetime.now(UTC),
        requirements=(),
    )
    store = InMemoryParseRunStore(existing)
    dispatcher = RecordingDispatcher()
    service = ParseRunService(InMemoryJobReader(job), store, dispatcher)

    run = await service.submit_parse_run(job.user_id, job.id, "parse-key")

    assert run == existing
    assert not store.committed
    assert dispatcher.dispatched == [existing.id]


@pytest.mark.asyncio
async def test_submit_parse_run_keeps_queued_run_when_dispatch_fails() -> None:
    job = make_job()
    store = InMemoryParseRunStore()
    service = ParseRunService(InMemoryJobReader(job), store, RecordingDispatcher(fail=True))

    with pytest.raises(ParseRunDispatchError):
        await service.submit_parse_run(job.user_id, job.id, "parse-key")

    assert store.existing is not None
    assert store.existing.status == ParseRunStatus.QUEUED
    assert store.committed


@pytest.mark.asyncio
async def test_submit_parse_run_rejects_key_reuse_after_job_input_changes() -> None:
    original = make_job()
    existing = ParseRunRecord(
        id=uuid4(),
        user_id=original.user_id,
        job_id=original.id,
        status=ParseRunStatus.SUCCEEDED,
        idempotency_key="parse-key",
        input_fingerprint=compute_parse_input_fingerprint(original),
        model_name=FAKE_PARSE_MODEL_NAME,
        prompt_version=PARSE_PROMPT_VERSION,
        attempt=1,
        error_code=None,
        latency_ms=0,
        input_tokens=None,
        output_tokens=None,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        requirements=(),
    )
    changed_description = "Go experience required."
    changed = replace(
        original,
        raw_description=changed_description,
        description_hash=compute_description_hash(changed_description),
        version=original.version + 1,
    )
    service = ParseRunService(
        InMemoryJobReader(changed),
        InMemoryParseRunStore(existing),
        RecordingDispatcher(),
    )

    with pytest.raises(IdempotencyKeyConflictError):
        await service.submit_parse_run(changed.user_id, changed.id, "parse-key")


@pytest.mark.asyncio
async def test_submit_parse_run_requires_owned_job() -> None:
    job = make_job()
    service = ParseRunService(
        InMemoryJobReader(job),
        InMemoryParseRunStore(),
        RecordingDispatcher(),
    )

    with pytest.raises(JobNotFoundError):
        await service.submit_parse_run(uuid4(), job.id, "parse-key")


@pytest.mark.asyncio
async def test_get_parse_run_raises_not_found_for_missing_run() -> None:
    job = make_job()
    service = ParseRunService(
        InMemoryJobReader(job),
        InMemoryParseRunStore(),
        RecordingDispatcher(),
    )

    with pytest.raises(ParseRunNotFoundError):
        await service.get_parse_run(job.user_id, job.id, uuid4())
