from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import AnalysisRun, EvidenceMatch, Experience, JobRequirement, ParseRun
from careerops.domain.analysis_runs import (
    AnalysisInput,
    AnalysisRunCreationResult,
    AnalysisRunErrorCode,
    AnalysisRunRecord,
    AnalysisRunRecoveryItem,
    AnalysisRunStatus,
    AnalysisRunWorkItem,
    EvidenceMatchRecord,
    matcher_model_name_from_pipeline,
)
from careerops.domain.evidence_matching import EvidenceVerdict
from careerops.domain.parse_runs import ParseRunRecord
from careerops.repositories.experiences import to_record as to_experience_record
from careerops.repositories.parse_runs import to_requirement_record


class AnalysisRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_analysis_run_by_idempotency_key(
        self,
        user_id: UUID,
        job_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRunRecord | None:
        result = await self._session.execute(
            select(AnalysisRun).where(
                AnalysisRun.user_id == user_id,
                AnalysisRun.job_id == job_id,
                AnalysisRun.idempotency_key == idempotency_key,
            )
        )
        run = result.scalar_one_or_none()
        return None if run is None else await self._to_record(run)

    async def get_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        analysis_run_id: UUID,
    ) -> AnalysisRunRecord | None:
        result = await self._session.execute(
            select(AnalysisRun).where(
                AnalysisRun.id == analysis_run_id,
                AnalysisRun.user_id == user_id,
                AnalysisRun.job_id == job_id,
            )
        )
        run = result.scalar_one_or_none()
        return None if run is None else await self._to_record(run)

    async def create_or_get_queued_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run: ParseRunRecord,
        idempotency_key: str,
        input_fingerprint: str,
        prompt_version: str,
    ) -> AnalysisRunCreationResult:
        analysis_run_id = uuid4()
        result = await self._session.execute(
            insert(AnalysisRun)
            .values(
                id=analysis_run_id,
                user_id=user_id,
                job_id=job_id,
                parse_run_id=parse_run.id,
                status=AnalysisRunStatus.QUEUED.value,
                idempotency_key=idempotency_key,
                input_fingerprint=input_fingerprint,
                model_name=matcher_model_name_from_pipeline(prompt_version),
                prompt_version=prompt_version,
                attempt=1,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    AnalysisRun.user_id,
                    AnalysisRun.job_id,
                    AnalysisRun.idempotency_key,
                ]
            )
            .returning(AnalysisRun.id)
        )
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            existing = await self.get_analysis_run_by_idempotency_key(
                user_id,
                job_id,
                idempotency_key,
            )
            if existing is None:
                raise RuntimeError("Analysis run conflict did not resolve to an existing run.")
            return AnalysisRunCreationResult(run=existing, created=False)

        created = await self.get_analysis_run(user_id, job_id, analysis_run_id)
        if created is None:
            raise RuntimeError("Inserted analysis run could not be loaded.")
        return AnalysisRunCreationResult(run=created, created=True)

    async def claim_analysis_run(self, analysis_run_id: UUID) -> AnalysisRunWorkItem | None:
        result = await self._session.execute(
            update(AnalysisRun)
            .where(
                AnalysisRun.id == analysis_run_id,
                AnalysisRun.status == AnalysisRunStatus.QUEUED.value,
            )
            .values(status=AnalysisRunStatus.RUNNING.value, started_at=datetime.now(UTC))
            .returning(
                AnalysisRun.id,
                AnalysisRun.attempt,
                AnalysisRun.user_id,
                AnalysisRun.job_id,
                AnalysisRun.parse_run_id,
                AnalysisRun.input_fingerprint,
                AnalysisRun.model_name,
                AnalysisRun.prompt_version,
                AnalysisRun.created_at,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return AnalysisRunWorkItem(
            id=row.id,
            attempt=row.attempt,
            user_id=row.user_id,
            job_id=row.job_id,
            parse_run_id=row.parse_run_id,
            input_fingerprint=row.input_fingerprint,
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            created_at=row.created_at,
        )

    async def load_analysis_input(self, work_item: AnalysisRunWorkItem) -> AnalysisInput:
        parse_input_fingerprint = await self._session.scalar(
            select(ParseRun.input_fingerprint).where(ParseRun.id == work_item.parse_run_id)
        )
        if parse_input_fingerprint is None:
            raise RuntimeError("Analysis run references a missing parse run.")
        requirements_result = await self._session.execute(
            select(JobRequirement)
            .where(
                JobRequirement.job_id == work_item.job_id,
                JobRequirement.parse_run_id == work_item.parse_run_id,
            )
            .order_by(JobRequirement.source_span_start.asc(), JobRequirement.id.asc())
        )
        experiences_result = await self._session.execute(
            select(Experience)
            .where(
                Experience.user_id == work_item.user_id,
                Experience.deleted_at.is_(None),
            )
            .order_by(Experience.id.asc())
        )
        return AnalysisInput(
            parse_input_fingerprint=parse_input_fingerprint,
            requirements=tuple(
                to_requirement_record(requirement)
                for requirement in requirements_result.scalars().all()
            ),
            experiences=tuple(
                to_experience_record(experience)
                for experience in experiences_result.scalars().all()
            ),
        )

    async def fail_analysis_run(
        self,
        analysis_run_id: UUID,
        attempt: int,
        model_name: str,
        error_code: AnalysisRunErrorCode,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> bool:
        result = await self._session.execute(
            update(AnalysisRun)
            .where(
                AnalysisRun.id == analysis_run_id,
                AnalysisRun.status == AnalysisRunStatus.RUNNING.value,
                AnalysisRun.attempt == attempt,
            )
            .values(
                status=AnalysisRunStatus.FAILED.value,
                model_name=model_name,
                error_code=error_code.value,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finished_at=datetime.now(UTC),
            )
            .returning(AnalysisRun.id)
        )
        return result.scalar_one_or_none() is not None

    async def requeue_stale_analysis_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[AnalysisRunRecoveryItem]:
        stale_ids = (
            select(AnalysisRun.id)
            .where(
                AnalysisRun.status == AnalysisRunStatus.RUNNING.value,
                AnalysisRun.started_at < stale_before,
            )
            .order_by(AnalysisRun.started_at.asc(), AnalysisRun.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.id.in_(stale_ids))
            .values(
                status=AnalysisRunStatus.QUEUED.value,
                attempt=AnalysisRun.attempt + 1,
                error_code=None,
                latency_ms=None,
                started_at=None,
                finished_at=None,
            )
            .returning(AnalysisRun.id, AnalysisRun.attempt)
        )
        return [
            AnalysisRunRecoveryItem(id=row.id, attempt=row.attempt)
            for row in result.all()
        ]

    async def list_queued_analysis_run_ids(self, limit: int) -> list[UUID]:
        result = await self._session.execute(
            select(AnalysisRun.id)
            .where(AnalysisRun.status == AnalysisRunStatus.QUEUED.value)
            .order_by(AnalysisRun.created_at.asc(), AnalysisRun.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()

    async def _to_record(self, run: AnalysisRun) -> AnalysisRunRecord:
        result = await self._session.execute(
            select(EvidenceMatch, JobRequirement)
            .join(JobRequirement, JobRequirement.id == EvidenceMatch.requirement_id)
            .where(EvidenceMatch.analysis_run_id == run.id)
            .order_by(JobRequirement.source_span_start.asc(), EvidenceMatch.id.asc())
        )
        matches = tuple(to_evidence_match_record(match) for match, _ in result.all())
        return AnalysisRunRecord(
            id=run.id,
            user_id=run.user_id,
            job_id=run.job_id,
            parse_run_id=run.parse_run_id,
            status=AnalysisRunStatus(run.status),
            idempotency_key=run.idempotency_key,
            input_fingerprint=run.input_fingerprint,
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            attempt=run.attempt,
            validation_failure_count=run.validation_failure_count,
            error_code=run.error_code,
            latency_ms=run.latency_ms,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
            matches=matches,
        )


def to_evidence_match_record(match: EvidenceMatch) -> EvidenceMatchRecord:
    confidence = match.confidence
    return EvidenceMatchRecord(
        id=match.id,
        requirement_id=match.requirement_id,
        experience_id=match.experience_id,
        experience_version=match.experience_version,
        verdict=EvidenceVerdict(match.verdict),
        quote=match.quote,
        quote_valid=match.quote_valid,
        confidence=float(confidence) if isinstance(confidence, Decimal) else confidence,
    )
