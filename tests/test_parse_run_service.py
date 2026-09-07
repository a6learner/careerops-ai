from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import (
    IdempotencyKeyConflictError,
    JobNotFoundError,
    ParseRunNotFoundError,
)
from careerops.domain.jobs import JobRecord, JobStatus
from careerops.domain.parse_runs import (
    FAKE_PARSE_MODEL_NAME,
    PARSE_PROMPT_VERSION,
    JobRequirementRecord,
    ParsedRequirement,
    ParseRunCreationResult,
    ParseRunRecord,
    ParseRunStatus,
    RequirementCategory,
)
from careerops.services.jobs import compute_description_hash
from careerops.services.parse_runs import (
    ParseRunService,
    compute_parse_input_fingerprint,
    parse_requirements_deterministically,
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
        self.created_requirements: tuple[ParsedRequirement, ...] = ()

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

    async def create_or_get_succeeded_parse_run(
        self,
        user_id: UUID,
        job: JobRecord,
        idempotency_key: str,
        input_fingerprint: str,
        requirements: tuple[ParsedRequirement, ...],
        latency_ms: int,
    ) -> ParseRunCreationResult:
        self.created_requirements = requirements
        now = datetime.now(UTC)
        records = tuple(
            JobRequirementRecord(
                id=uuid4(),
                job_id=job.id,
                parse_run_id=uuid4(),
                category=requirement.category,
                text=requirement.text,
                skill_normalized=requirement.skill_normalized,
                source_span_start=requirement.source_span_start,
                source_span_end=requirement.source_span_end,
            )
            for requirement in requirements
        )
        self.existing = ParseRunRecord(
            id=uuid4(),
            user_id=user_id,
            job_id=job.id,
            status=ParseRunStatus.SUCCEEDED,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
            model_name=FAKE_PARSE_MODEL_NAME,
            prompt_version=PARSE_PROMPT_VERSION,
            attempt=1,
            error_code=None,
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            started_at=now,
            finished_at=now,
            created_at=now,
            requirements=records,
        )
        return ParseRunCreationResult(run=self.existing, created=True)

    async def commit(self) -> None:
        self.committed = True


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


def test_fake_parser_returns_requirements_with_source_spans() -> None:
    raw_description = "Python experience required. Preferred Redis."

    requirements = parse_requirements_deterministically(raw_description)

    assert [requirement.text for requirement in requirements] == [
        "Python experience required",
        "Preferred Redis",
    ]
    assert requirements[0].category == RequirementCategory.MUST_HAVE
    assert requirements[1].category == RequirementCategory.NICE_TO_HAVE
    assert requirements[0].skill_normalized == "python"
    source_text = raw_description[
        requirements[0].source_span_start : requirements[0].source_span_end
    ]
    assert " ".join(source_text.split()) == requirements[0].text


@pytest.mark.asyncio
async def test_submit_parse_run_creates_succeeded_run_and_commits() -> None:
    job = make_job()
    store = InMemoryParseRunStore()
    service = ParseRunService(InMemoryJobReader(job), store)

    run = await service.submit_parse_run(job.user_id, job.id, "parse-key")

    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.input_fingerprint == compute_parse_input_fingerprint(job)
    assert run.model_name == FAKE_PARSE_MODEL_NAME
    assert len(run.requirements) == 2
    assert store.created_requirements
    assert store.committed


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
    service = ParseRunService(InMemoryJobReader(job), store)

    run = await service.submit_parse_run(job.user_id, job.id, "parse-key")

    assert run == existing
    assert not store.committed


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
    service = ParseRunService(InMemoryJobReader(changed), InMemoryParseRunStore(existing))

    with pytest.raises(IdempotencyKeyConflictError):
        await service.submit_parse_run(changed.user_id, changed.id, "parse-key")


@pytest.mark.asyncio
async def test_submit_parse_run_requires_owned_job() -> None:
    job = make_job()
    service = ParseRunService(InMemoryJobReader(job), InMemoryParseRunStore())

    with pytest.raises(JobNotFoundError):
        await service.submit_parse_run(uuid4(), job.id, "parse-key")


@pytest.mark.asyncio
async def test_get_parse_run_raises_not_found_for_missing_run() -> None:
    job = make_job()
    service = ParseRunService(InMemoryJobReader(job), InMemoryParseRunStore())

    with pytest.raises(ParseRunNotFoundError):
        await service.get_parse_run(job.user_id, job.id, uuid4())
