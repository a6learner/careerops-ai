from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import JobRequirement, ParseRun
from careerops.domain.jobs import JobRecord
from careerops.domain.parse_runs import (
    FAKE_PARSE_MODEL_NAME,
    PARSE_PROMPT_VERSION,
    JobRequirementRecord,
    ParsedRequirement,
    ParseRunRecord,
    ParseRunStatus,
    RequirementCategory,
)


class ParseRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_parse_run_by_idempotency_key(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord | None:
        result = await self._session.execute(
            select(ParseRun).where(
                ParseRun.user_id == user_id,
                ParseRun.idempotency_key == idempotency_key,
            )
        )
        parse_run = result.scalar_one_or_none()
        if parse_run is None:
            return None
        return await self._to_record(parse_run)

    async def get_parse_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
    ) -> ParseRunRecord | None:
        result = await self._session.execute(
            select(ParseRun).where(
                ParseRun.id == parse_run_id,
                ParseRun.user_id == user_id,
                ParseRun.job_id == job_id,
            )
        )
        parse_run = result.scalar_one_or_none()
        if parse_run is None:
            return None
        return await self._to_record(parse_run)

    async def create_succeeded_parse_run(
        self,
        user_id: UUID,
        job: JobRecord,
        idempotency_key: str,
        input_fingerprint: str,
        requirements: tuple[ParsedRequirement, ...],
        latency_ms: int,
    ) -> ParseRunRecord:
        now = datetime.now(UTC)
        parse_run = ParseRun(
            user_id=user_id,
            job_id=job.id,
            status=ParseRunStatus.SUCCEEDED.value,
            idempotency_key=idempotency_key,
            input_fingerprint=input_fingerprint,
            model_name=FAKE_PARSE_MODEL_NAME,
            prompt_version=PARSE_PROMPT_VERSION,
            attempt=1,
            latency_ms=latency_ms,
            started_at=now,
            finished_at=now,
        )
        self._session.add(parse_run)
        await self._session.flush()

        for requirement in requirements:
            self._session.add(
                JobRequirement(
                    job_id=job.id,
                    parse_run_id=parse_run.id,
                    category=requirement.category.value,
                    text=requirement.text,
                    skill_normalized=requirement.skill_normalized,
                    source_span_start=requirement.source_span_start,
                    source_span_end=requirement.source_span_end,
                )
            )

        await self._session.flush()
        await self._session.refresh(parse_run)
        return await self._to_record(parse_run)

    async def commit(self) -> None:
        await self._session.commit()

    async def _to_record(self, parse_run: ParseRun) -> ParseRunRecord:
        result = await self._session.execute(
            select(JobRequirement)
            .where(JobRequirement.parse_run_id == parse_run.id)
            .order_by(JobRequirement.source_span_start.asc(), JobRequirement.id.asc())
        )
        requirements = tuple(to_requirement_record(row) for row in result.scalars().all())
        return ParseRunRecord(
            id=parse_run.id,
            user_id=parse_run.user_id,
            job_id=parse_run.job_id,
            status=ParseRunStatus(parse_run.status),
            idempotency_key=parse_run.idempotency_key,
            input_fingerprint=parse_run.input_fingerprint,
            model_name=parse_run.model_name,
            prompt_version=parse_run.prompt_version,
            attempt=parse_run.attempt,
            error_code=parse_run.error_code,
            latency_ms=parse_run.latency_ms,
            input_tokens=parse_run.input_tokens,
            output_tokens=parse_run.output_tokens,
            started_at=parse_run.started_at,
            finished_at=parse_run.finished_at,
            created_at=parse_run.created_at,
            requirements=requirements,
        )


def to_requirement_record(requirement: JobRequirement) -> JobRequirementRecord:
    return JobRequirementRecord(
        id=requirement.id,
        job_id=requirement.job_id,
        parse_run_id=requirement.parse_run_id,
        category=RequirementCategory(requirement.category),
        text=requirement.text,
        skill_normalized=requirement.skill_normalized,
        source_span_start=requirement.source_span_start,
        source_span_end=requirement.source_span_end,
    )
