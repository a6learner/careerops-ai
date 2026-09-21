from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import Experience, ExperienceEmbeddingRun
from careerops.domain.embeddings import (
    EmbeddingRunErrorCode,
    EmbeddingRunStatus,
    EmbeddingRunWorkItem,
)
from careerops.domain.experiences import ExperienceRecord
from careerops.repositories.experiences import to_record


class EmbeddingRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        experience: ExperienceRecord,
        model_name: str,
        input_version: str,
    ) -> UUID:
        run = ExperienceEmbeddingRun(
            user_id=experience.user_id,
            experience_id=experience.id,
            experience_version=experience.version,
            content_hash=experience.content_hash,
            status=EmbeddingRunStatus.QUEUED.value,
            model_name=model_name,
            input_version=input_version,
            attempt=1,
        )
        self._session.add(run)
        await self._session.flush()
        return run.id

    async def supersede_active_runs(self, user_id: UUID, experience_id: UUID) -> None:
        await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(
                ExperienceEmbeddingRun.user_id == user_id,
                ExperienceEmbeddingRun.experience_id == experience_id,
                ExperienceEmbeddingRun.status.in_(
                    [EmbeddingRunStatus.QUEUED.value, EmbeddingRunStatus.RUNNING.value]
                ),
            )
            .values(
                status=EmbeddingRunStatus.SUPERSEDED.value,
                error_code=None,
                finished_at=datetime.now(UTC),
            )
        )

    async def claim_run(self, run_id: UUID) -> EmbeddingRunWorkItem | None:
        result = await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(
                ExperienceEmbeddingRun.id == run_id,
                ExperienceEmbeddingRun.status == EmbeddingRunStatus.QUEUED.value,
            )
            .values(
                status=EmbeddingRunStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
            .returning(
                ExperienceEmbeddingRun.id,
                ExperienceEmbeddingRun.user_id,
                ExperienceEmbeddingRun.experience_id,
                ExperienceEmbeddingRun.experience_version,
                ExperienceEmbeddingRun.content_hash,
                ExperienceEmbeddingRun.model_name,
                ExperienceEmbeddingRun.input_version,
                ExperienceEmbeddingRun.attempt,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None

        experience_result = await self._session.execute(
            select(Experience).where(
                Experience.id == row.experience_id,
                Experience.user_id == row.user_id,
                Experience.version == row.experience_version,
                Experience.content_hash == row.content_hash,
                Experience.deleted_at.is_(None),
            )
        )
        experience = experience_result.scalar_one_or_none()
        if experience is None:
            await self._mark_superseded(row.id, row.attempt)
            return None
        return EmbeddingRunWorkItem(
            id=row.id,
            attempt=row.attempt,
            experience=to_record(experience),
            model_name=row.model_name,
            input_version=row.input_version,
        )

    async def complete_run(
        self,
        work_item: EmbeddingRunWorkItem,
        vector: tuple[float, ...],
    ) -> bool:
        run_result = await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(
                ExperienceEmbeddingRun.id == work_item.id,
                ExperienceEmbeddingRun.status == EmbeddingRunStatus.RUNNING.value,
                ExperienceEmbeddingRun.attempt == work_item.attempt,
            )
            .values(
                status=EmbeddingRunStatus.SUCCEEDED.value,
                finished_at=datetime.now(UTC),
            )
            .returning(ExperienceEmbeddingRun.id)
        )
        if run_result.scalar_one_or_none() is None:
            return False

        experience = work_item.experience
        experience_result = await self._session.execute(
            update(Experience)
            .where(
                Experience.id == experience.id,
                Experience.user_id == experience.user_id,
                Experience.version == experience.version,
                Experience.content_hash == experience.content_hash,
                Experience.deleted_at.is_(None),
            )
            .values(
                embedding=list(vector),
                embedding_content_hash=experience.content_hash,
                embedding_model=work_item.model_name,
                embedding_input_version=work_item.input_version,
                embedded_at=datetime.now(UTC),
            )
            .returning(Experience.id)
        )
        if experience_result.scalar_one_or_none() is not None:
            return True

        await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(
                ExperienceEmbeddingRun.id == work_item.id,
                ExperienceEmbeddingRun.status == EmbeddingRunStatus.SUCCEEDED.value,
                ExperienceEmbeddingRun.attempt == work_item.attempt,
            )
            .values(
                status=EmbeddingRunStatus.SUPERSEDED.value,
                finished_at=datetime.now(UTC),
            )
        )
        return False

    async def fail_run(
        self,
        work_item: EmbeddingRunWorkItem,
        error_code: EmbeddingRunErrorCode,
    ) -> bool:
        result = await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(
                ExperienceEmbeddingRun.id == work_item.id,
                ExperienceEmbeddingRun.status == EmbeddingRunStatus.RUNNING.value,
                ExperienceEmbeddingRun.attempt == work_item.attempt,
            )
            .values(
                status=EmbeddingRunStatus.FAILED.value,
                error_code=error_code.value,
                finished_at=datetime.now(UTC),
            )
            .returning(ExperienceEmbeddingRun.id)
        )
        return result.scalar_one_or_none() is not None

    async def requeue_stale_runs(self, stale_before: datetime, limit: int) -> list[UUID]:
        stale_ids = (
            select(ExperienceEmbeddingRun.id)
            .where(
                ExperienceEmbeddingRun.status == EmbeddingRunStatus.RUNNING.value,
                ExperienceEmbeddingRun.started_at < stale_before,
            )
            .order_by(
                ExperienceEmbeddingRun.started_at.asc(),
                ExperienceEmbeddingRun.id.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(ExperienceEmbeddingRun.id.in_(stale_ids))
            .values(
                status=EmbeddingRunStatus.QUEUED.value,
                attempt=ExperienceEmbeddingRun.attempt + 1,
                error_code=None,
                started_at=None,
                finished_at=None,
            )
            .returning(ExperienceEmbeddingRun.id)
        )
        return list(result.scalars().all())

    async def reconcile_missing_runs(
        self,
        model_name: str,
        input_version: str,
        limit: int,
    ) -> list[UUID]:
        active_run_exists = exists().where(
            ExperienceEmbeddingRun.experience_id == Experience.id,
            ExperienceEmbeddingRun.status.in_(
                [EmbeddingRunStatus.QUEUED.value, EmbeddingRunStatus.RUNNING.value]
            ),
        )
        target_run_exists = exists().where(
            ExperienceEmbeddingRun.experience_id == Experience.id,
            ExperienceEmbeddingRun.experience_version == Experience.version,
            ExperienceEmbeddingRun.content_hash == Experience.content_hash,
            ExperienceEmbeddingRun.model_name == model_name,
            ExperienceEmbeddingRun.input_version == input_version,
        )
        result = await self._session.execute(
            select(Experience)
            .where(
                Experience.deleted_at.is_(None),
                or_(
                    Experience.embedding.is_(None),
                    Experience.embedding_content_hash.is_distinct_from(Experience.content_hash),
                    Experience.embedding_model.is_distinct_from(model_name),
                    Experience.embedding_input_version.is_distinct_from(input_version),
                ),
                ~active_run_exists,
                ~target_run_exists,
            )
            .order_by(Experience.created_at.asc(), Experience.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        run_ids: list[UUID] = []
        for experience in result.scalars().all():
            await self._session.execute(
                update(Experience)
                .where(
                    Experience.id == experience.id,
                    Experience.version == experience.version,
                    Experience.content_hash == experience.content_hash,
                    Experience.deleted_at.is_(None),
                )
                .values(
                    embedding=None,
                    embedding_content_hash=None,
                    embedding_model=None,
                    embedding_input_version=None,
                    embedded_at=None,
                )
            )
            run_id = uuid4()
            inserted = await self._session.execute(
                insert(ExperienceEmbeddingRun)
                .values(
                    id=run_id,
                    user_id=experience.user_id,
                    experience_id=experience.id,
                    experience_version=experience.version,
                    content_hash=experience.content_hash,
                    status=EmbeddingRunStatus.QUEUED.value,
                    model_name=model_name,
                    input_version=input_version,
                    attempt=1,
                )
                .on_conflict_do_nothing()
                .returning(ExperienceEmbeddingRun.id)
            )
            inserted_id = inserted.scalar_one_or_none()
            if inserted_id is not None:
                run_ids.append(inserted_id)
        return run_ids

    async def list_queued_run_ids(self, limit: int) -> list[UUID]:
        result = await self._session.execute(
            select(ExperienceEmbeddingRun.id)
            .where(ExperienceEmbeddingRun.status == EmbeddingRunStatus.QUEUED.value)
            .order_by(ExperienceEmbeddingRun.created_at.asc(), ExperienceEmbeddingRun.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()

    async def _mark_superseded(self, run_id: UUID, attempt: int) -> None:
        await self._session.execute(
            update(ExperienceEmbeddingRun)
            .where(
                ExperienceEmbeddingRun.id == run_id,
                ExperienceEmbeddingRun.status == EmbeddingRunStatus.RUNNING.value,
                ExperienceEmbeddingRun.attempt == attempt,
            )
            .values(
                status=EmbeddingRunStatus.SUPERSEDED.value,
                finished_at=datetime.now(UTC),
            )
        )
