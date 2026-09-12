import hashlib
from typing import Protocol
from uuid import UUID

from careerops.domain.analysis_runs import (
    ANALYSIS_PROMPT_VERSION,
    AnalysisRunCreationResult,
    AnalysisRunRecord,
    AnalysisRunStatus,
)
from careerops.domain.errors import (
    AnalysisRunNotFoundError,
    IdempotencyKeyConflictError,
    JobNotFoundError,
    NoActiveExperiencesError,
    ParseRunNotFoundError,
    ParseRunNotReadyError,
)
from careerops.domain.experiences import ExperienceRecord
from careerops.domain.jobs import JobRecord
from careerops.domain.parse_runs import ParseRunRecord, ParseRunStatus


class AnalysisJobReader(Protocol):
    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None: ...


class AnalysisParseRunReader(Protocol):
    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord | None: ...


class AnalysisExperienceReader(Protocol):
    async def list_experiences(self, user_id: UUID) -> list[ExperienceRecord]: ...


class AnalysisRunStore(Protocol):
    async def get_analysis_run_by_idempotency_key(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRunRecord | None: ...

    async def get_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        analysis_run_id: UUID,
    ) -> AnalysisRunRecord | None: ...

    async def create_or_get_queued_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run: ParseRunRecord,
        idempotency_key: str,
        input_fingerprint: str,
    ) -> AnalysisRunCreationResult: ...

    async def commit(self) -> None: ...


class AnalysisRunDispatcher(Protocol):
    async def dispatch(self, analysis_run_id: UUID) -> None: ...


class AnalysisRunService:
    def __init__(
        self,
        jobs: AnalysisJobReader,
        parse_runs: AnalysisParseRunReader,
        experiences: AnalysisExperienceReader,
        analysis_runs: AnalysisRunStore,
        dispatcher: AnalysisRunDispatcher,
    ) -> None:
        self._jobs = jobs
        self._parse_runs = parse_runs
        self._experiences = experiences
        self._analysis_runs = analysis_runs
        self._dispatcher = dispatcher

    async def submit_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRunRecord:
        job = await self._jobs.get_job(user_id, job_id)
        if job is None:
            raise JobNotFoundError()

        parse_run = await self._parse_runs.get_parse_run(user_id, job_id, parse_run_id)
        if parse_run is None:
            raise ParseRunNotFoundError()
        if parse_run.status is not ParseRunStatus.SUCCEEDED or not parse_run.requirements:
            raise ParseRunNotReadyError()

        experiences = tuple(await self._experiences.list_experiences(user_id))
        input_fingerprint = compute_analysis_input_fingerprint(parse_run, experiences)
        existing = await self._analysis_runs.get_analysis_run_by_idempotency_key(
            user_id,
            job_id,
            idempotency_key,
        )
        if existing is not None:
            ensure_matching_analysis_input(existing, input_fingerprint)
            if existing.status is AnalysisRunStatus.QUEUED:
                await self._dispatcher.dispatch(existing.id)
            return existing

        if not experiences:
            raise NoActiveExperiencesError()

        creation = await self._analysis_runs.create_or_get_queued_analysis_run(
            user_id,
            job_id,
            parse_run,
            idempotency_key,
            input_fingerprint,
        )
        ensure_matching_analysis_input(creation.run, input_fingerprint)
        if creation.created:
            await self._analysis_runs.commit()
        if creation.run.status is AnalysisRunStatus.QUEUED:
            await self._dispatcher.dispatch(creation.run.id)
        return creation.run

    async def get_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        analysis_run_id: UUID,
    ) -> AnalysisRunRecord:
        if await self._jobs.get_job(user_id, job_id) is None:
            raise JobNotFoundError()
        run = await self._analysis_runs.get_analysis_run(user_id, job_id, analysis_run_id)
        if run is None:
            raise AnalysisRunNotFoundError()
        return run


def compute_analysis_input_fingerprint(
    parse_run: ParseRunRecord,
    experiences: tuple[ExperienceRecord, ...],
) -> str:
    return compute_analysis_fingerprint(
        parse_run.id,
        parse_run.input_fingerprint,
        experiences,
    )


def compute_analysis_fingerprint(
    parse_run_id: UUID,
    parse_input_fingerprint: str,
    experiences: tuple[ExperienceRecord, ...],
) -> str:
    experience_state = "\n".join(
        f"{experience.id}:{experience.version}:{experience.content_hash}"
        for experience in sorted(experiences, key=lambda item: str(item.id))
    )
    raw = (
        f"{parse_run_id}:{parse_input_fingerprint}:{ANALYSIS_PROMPT_VERSION}\n"
        f"{experience_state}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_matching_analysis_input(run: AnalysisRunRecord, input_fingerprint: str) -> None:
    if run.input_fingerprint != input_fingerprint:
        raise IdempotencyKeyConflictError()
