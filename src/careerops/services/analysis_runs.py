import hashlib
import logging
from typing import Protocol
from uuid import UUID

from careerops.domain.analysis_runs import (
    ANALYSIS_PROMPT_VERSION,
    FAKE_ANALYSIS_MODEL_NAME,
    AnalysisDispatchSource,
    AnalysisRateLimitReservation,
    AnalysisRunCreationResult,
    AnalysisRunRecord,
    AnalysisRunStatus,
    matcher_pipeline_version,
)
from careerops.domain.embeddings import (
    FAKE_EMBEDDING_SPACE,
    EmbeddingSpace,
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

logger = logging.getLogger(__name__)


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
        prompt_version: str,
    ) -> AnalysisRunCreationResult: ...

    async def commit(self) -> None: ...


class AnalysisRunDispatcher(Protocol):
    async def dispatch(
        self,
        analysis_run_id: UUID,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
    ) -> None: ...


class AnalysisRateLimiter(Protocol):
    async def reserve(self, user_id: UUID) -> AnalysisRateLimitReservation: ...

    async def release(
        self,
        user_id: UUID,
        reservation: AnalysisRateLimitReservation,
    ) -> None: ...


class AnalysisRunService:
    def __init__(
        self,
        jobs: AnalysisJobReader,
        parse_runs: AnalysisParseRunReader,
        experiences: AnalysisExperienceReader,
        analysis_runs: AnalysisRunStore,
        dispatcher: AnalysisRunDispatcher,
        rate_limiter: AnalysisRateLimiter,
        retrieval_space: EmbeddingSpace = FAKE_EMBEDDING_SPACE,
        matcher_model_name: str = FAKE_ANALYSIS_MODEL_NAME,
    ) -> None:
        self._jobs = jobs
        self._parse_runs = parse_runs
        self._experiences = experiences
        self._analysis_runs = analysis_runs
        self._dispatcher = dispatcher
        self._rate_limiter = rate_limiter
        self._prompt_version = matcher_pipeline_version(
            retrieval_space,
            matcher_model_name,
        )

    async def submit_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
        idempotency_key: str,
        request_id: str = "unknown",
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
        input_fingerprint = compute_analysis_input_fingerprint(
            parse_run,
            experiences,
            self._prompt_version,
        )
        existing = await self._analysis_runs.get_analysis_run_by_idempotency_key(
            user_id,
            job_id,
            idempotency_key,
        )
        if existing is not None:
            ensure_matching_analysis_input(existing, input_fingerprint)
            log_analysis_run_accepted(existing, request_id, outcome="idempotent_replay")
            if existing.status is AnalysisRunStatus.QUEUED:
                await self._dispatcher.dispatch(
                    existing.id,
                    request_id,
                    AnalysisDispatchSource.IDEMPOTENT_REPLAY,
                )
            return existing

        if not experiences:
            raise NoActiveExperiencesError()

        reservation = await self._rate_limiter.reserve(user_id)
        creation: AnalysisRunCreationResult | None = None
        try:
            creation = await self._analysis_runs.create_or_get_queued_analysis_run(
                user_id,
                job_id,
                parse_run,
                idempotency_key,
                input_fingerprint,
                self._prompt_version,
            )
            ensure_matching_analysis_input(creation.run, input_fingerprint)
            if creation.created:
                await self._analysis_runs.commit()
        finally:
            if creation is None or not creation.created:
                await self._rate_limiter.release(user_id, reservation)
        outcome = "created" if creation.created else "concurrent_replay"
        log_analysis_run_accepted(creation.run, request_id, outcome=outcome)
        if creation.run.status is AnalysisRunStatus.QUEUED:
            await self._dispatcher.dispatch(
                creation.run.id,
                request_id,
                (
                    AnalysisDispatchSource.SUBMISSION
                    if creation.created
                    else AnalysisDispatchSource.IDEMPOTENT_REPLAY
                ),
            )
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
    prompt_version: str = ANALYSIS_PROMPT_VERSION,
) -> str:
    return compute_analysis_fingerprint(
        parse_run.id,
        parse_run.input_fingerprint,
        experiences,
        prompt_version,
    )


def compute_analysis_fingerprint(
    parse_run_id: UUID,
    parse_input_fingerprint: str,
    experiences: tuple[ExperienceRecord, ...],
    prompt_version: str = ANALYSIS_PROMPT_VERSION,
) -> str:
    experience_state = "\n".join(
        f"{experience.id}:{experience.version}:{experience.content_hash}"
        for experience in sorted(experiences, key=lambda item: str(item.id))
    )
    raw = (
        f"{parse_run_id}:{parse_input_fingerprint}:{prompt_version}\n"
        f"{experience_state}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_matching_analysis_input(run: AnalysisRunRecord, input_fingerprint: str) -> None:
    if run.input_fingerprint != input_fingerprint:
        raise IdempotencyKeyConflictError()


def log_analysis_run_accepted(
    run: AnalysisRunRecord,
    request_id: str,
    *,
    outcome: str,
) -> None:
    logger.info(
        "analysis_run_accepted",
        extra={
            "request_id": request_id,
            "user_id": str(run.user_id),
            "run_type": "analysis",
            "run_id": str(run.id),
            "attempt": run.attempt,
            "pipeline_version": run.prompt_version,
            "model_name": run.model_name,
            "status": run.status.value,
            "outcome": outcome,
        },
    )
