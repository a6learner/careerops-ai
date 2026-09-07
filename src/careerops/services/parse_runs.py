import hashlib
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import (
    IdempotencyKeyConflictError,
    JobNotFoundError,
    ParseRunNotFoundError,
)
from careerops.domain.jobs import JobRecord
from careerops.domain.parse_runs import (
    PARSE_PROMPT_VERSION,
    ParseRunCreationResult,
    ParseRunRecord,
    ParseRunStatus,
)


class JobReader(Protocol):
    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None: ...


class ParseRunStore(Protocol):
    async def get_parse_run_by_idempotency_key(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord | None: ...

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord | None: ...

    async def create_or_get_queued_parse_run(
        self,
        user_id: UUID,
        job: JobRecord,
        idempotency_key: str,
        input_fingerprint: str,
    ) -> ParseRunCreationResult: ...

    async def commit(self) -> None: ...


class ParseRunDispatcher(Protocol):
    async def dispatch(self, parse_run_id: UUID) -> None: ...


class ParseRunService:
    def __init__(
        self,
        jobs: JobReader,
        parse_runs: ParseRunStore,
        dispatcher: ParseRunDispatcher,
    ) -> None:
        self._jobs = jobs
        self._parse_runs = parse_runs
        self._dispatcher = dispatcher

    async def submit_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord:
        job = await self._jobs.get_job(user_id, job_id)
        if job is None:
            raise JobNotFoundError()

        input_fingerprint = compute_parse_input_fingerprint(job)
        existing = await self._parse_runs.get_parse_run_by_idempotency_key(
            user_id=user_id,
            job_id=job_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            ensure_matching_idempotency_input(existing, input_fingerprint)
            if existing.status == ParseRunStatus.QUEUED:
                await self._dispatcher.dispatch(existing.id)
            return existing

        creation = await self._parse_runs.create_or_get_queued_parse_run(
            user_id=user_id,
            job=job,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
        )
        ensure_matching_idempotency_input(creation.run, input_fingerprint)
        if creation.created:
            await self._parse_runs.commit()
        if creation.run.status == ParseRunStatus.QUEUED:
            await self._dispatcher.dispatch(creation.run.id)
        return creation.run

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord:
        job = await self._jobs.get_job(user_id, job_id)
        if job is None:
            raise JobNotFoundError()

        run = await self._parse_runs.get_parse_run(
            user_id=user_id,
            job_id=job_id,
            parse_run_id=parse_run_id,
        )
        if run is None:
            raise ParseRunNotFoundError()
        return run


def ensure_matching_idempotency_input(run: ParseRunRecord, input_fingerprint: str) -> None:
    if run.input_fingerprint != input_fingerprint:
        raise IdempotencyKeyConflictError()


def compute_parse_input_fingerprint(job: JobRecord) -> str:
    raw = f"{job.id}:{job.version}:{job.description_hash}:{PARSE_PROMPT_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
