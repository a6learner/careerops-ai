from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import JobRequirement, ParseRun
from careerops.domain.jobs import JobRecord
from careerops.domain.parse_runs import (
    FAKE_PARSE_MODEL_NAME,
    PARSE_PROMPT_VERSION,
    JobRequirementRecord,
    ParsedRequirement,
    ParseRunCreationResult,
    ParseRunErrorCode,
    ParseRunRecord,
    ParseRunStatus,
    ParseRunWorkItem,
    RequirementCategory,
)


class ParseRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_parse_run_by_idempotency_key(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> ParseRunRecord | None:
        result = await self._session.execute(
            select(ParseRun).where(
                ParseRun.user_id == user_id,
                ParseRun.job_id == job_id,
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

    async def create_or_get_queued_parse_run(
        self,
        user_id: UUID,
        job: JobRecord,
        idempotency_key: str,
        input_fingerprint: str,
    ) -> ParseRunCreationResult:
        parse_run_id = uuid4()
        result = await self._session.execute(
            insert(ParseRun)
            .values(
                id=parse_run_id,
                user_id=user_id,
                job_id=job.id,
                status=ParseRunStatus.QUEUED.value,
                idempotency_key=idempotency_key,
                input_fingerprint=input_fingerprint,
                input_text=job.raw_description,
                model_name=FAKE_PARSE_MODEL_NAME,
                prompt_version=PARSE_PROMPT_VERSION,
                attempt=1,
            )
            .on_conflict_do_nothing(
                index_elements=[ParseRun.user_id, ParseRun.job_id, ParseRun.idempotency_key]
            )
            .returning(ParseRun.id)
        )
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            existing = await self.get_parse_run_by_idempotency_key(
                user_id=user_id,
                job_id=job.id,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise RuntimeError("Idempotency conflict did not resolve to an existing parse run.")
            return ParseRunCreationResult(run=existing, created=False)

        created = await self.get_parse_run(
            user_id=user_id,
            job_id=job.id,
            parse_run_id=parse_run_id,
        )
        if created is None:
            raise RuntimeError("Inserted parse run could not be loaded.")
        return ParseRunCreationResult(run=created, created=True)

    async def claim_parse_run(self, parse_run_id: UUID) -> ParseRunWorkItem | None:
        result = await self._session.execute(
            update(ParseRun)
            .where(
                ParseRun.id == parse_run_id,
                ParseRun.status == ParseRunStatus.QUEUED.value,
            )
            .values(
                status=ParseRunStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
            .returning(ParseRun.id, ParseRun.input_text)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return ParseRunWorkItem(id=row.id, input_text=row.input_text)

    async def complete_parse_run(
        self,
        parse_run_id: UUID,
        model_name: str,
        requirements: tuple[ParsedRequirement, ...],
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> bool:
        result = await self._session.execute(
            update(ParseRun)
            .where(
                ParseRun.id == parse_run_id,
                ParseRun.status == ParseRunStatus.RUNNING.value,
            )
            .values(
                status=ParseRunStatus.SUCCEEDED.value,
                model_name=model_name,
                error_code=None,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finished_at=datetime.now(UTC),
            )
            .returning(ParseRun.job_id)
        )
        job_id = result.scalar_one_or_none()
        if job_id is None:
            return False
        for requirement in requirements:
            self._session.add(
                JobRequirement(
                    job_id=job_id,
                    parse_run_id=parse_run_id,
                    category=requirement.category.value,
                    text=requirement.text,
                    skill_normalized=requirement.skill_normalized,
                    source_span_start=requirement.source_span_start,
                    source_span_end=requirement.source_span_end,
                )
            )
        await self._session.flush()
        return True

    async def fail_parse_run(
        self,
        parse_run_id: UUID,
        error_code: ParseRunErrorCode,
        latency_ms: int,
    ) -> bool:
        result = await self._session.execute(
            update(ParseRun)
            .where(
                ParseRun.id == parse_run_id,
                ParseRun.status == ParseRunStatus.RUNNING.value,
            )
            .values(
                status=ParseRunStatus.FAILED.value,
                error_code=error_code.value,
                latency_ms=latency_ms,
                finished_at=datetime.now(UTC),
            )
            .returning(ParseRun.id)
        )
        return result.scalar_one_or_none() is not None

    async def requeue_stale_parse_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[UUID]:
        stale_ids = (
            select(ParseRun.id)
            .where(
                ParseRun.status == ParseRunStatus.RUNNING.value,
                ParseRun.started_at < stale_before,
            )
            .order_by(ParseRun.started_at.asc(), ParseRun.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(
            update(ParseRun)
            .where(ParseRun.id.in_(stale_ids))
            .values(
                status=ParseRunStatus.QUEUED.value,
                attempt=ParseRun.attempt + 1,
                error_code=None,
                latency_ms=None,
                started_at=None,
                finished_at=None,
            )
            .returning(ParseRun.id)
        )
        return list(result.scalars().all())

    async def list_queued_parse_run_ids(self, limit: int) -> list[UUID]:
        result = await self._session.execute(
            select(ParseRun.id)
            .where(ParseRun.status == ParseRunStatus.QUEUED.value)
            .order_by(ParseRun.created_at.asc(), ParseRun.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
