from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Text, and_, cast, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import Project, ProjectCheckpoint
from careerops.domain.errors import IdempotencyKeyConflictError
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointRecord,
    ProjectInput,
    ProjectRecord,
    ProjectRecordConflictError,
    ProjectRecordNotFoundError,
    RecordCursor,
    RecordStatus,
    ReviewInput,
)


class ProjectRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_project(
        self, user_id: UUID, key: str, fingerprint: str, payload: ProjectInput
    ) -> ProjectRecord:
        await self._session.execute(
            insert(Project)
            .values(
                id=uuid4(),
                user_id=user_id,
                name=payload.name,
                goal=payload.goal,
                idempotency_key=key,
                request_fingerprint=fingerprint,
            )
            .on_conflict_do_nothing(index_elements=[Project.user_id, Project.idempotency_key])
        )
        row = (
            await self._session.execute(
                select(Project).where(Project.user_id == user_id, Project.idempotency_key == key)
            )
        ).scalar_one()
        if row.request_fingerprint != fingerprint:
            raise IdempotencyKeyConflictError()
        await self._session.commit()
        return project_record(row)

    async def get_project(self, user_id: UUID, project_id: UUID) -> ProjectRecord:
        row = (
            await self._session.execute(
                select(Project).where(Project.id == project_id, Project.user_id == user_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise ProjectRecordNotFoundError()
        return project_record(row)

    async def list_projects(
        self, user_id: UUID, cursor: RecordCursor | None, limit: int
    ) -> list[ProjectRecord]:
        statement = select(Project).where(Project.user_id == user_id)
        if cursor is not None:
            statement = statement.where(
                or_(
                    Project.created_at < cursor.created_at,
                    and_(Project.created_at == cursor.created_at, Project.id < cursor.id),
                )
            )
        rows = await self._session.scalars(
            statement.order_by(Project.created_at.desc(), Project.id.desc()).limit(limit)
        )
        return [project_record(row) for row in rows]

    async def create_checkpoint(
        self,
        user_id: UUID,
        project_id: UUID,
        key: str,
        fingerprint: str,
        payload: CheckpointInput,
    ) -> CheckpointRecord:
        await self._session.execute(
            insert(ProjectCheckpoint)
            .values(
                id=uuid4(),
                user_id=user_id,
                project_id=project_id,
                payload=payload.model_dump(mode="json"),
                content_sha256=fingerprint,
                idempotency_key=key,
                status=RecordStatus.DRAFT.value,
                version=1,
                contribution_note="",
            )
            .on_conflict_do_nothing(
                index_elements=[
                    ProjectCheckpoint.user_id,
                    ProjectCheckpoint.idempotency_key,
                ]
            )
        )
        row = (
            await self._session.execute(
                select(ProjectCheckpoint).where(
                    ProjectCheckpoint.user_id == user_id,
                    ProjectCheckpoint.idempotency_key == key,
                )
            )
        ).scalar_one()
        if row.project_id != project_id or row.content_sha256 != fingerprint:
            raise IdempotencyKeyConflictError()
        await self._session.commit()
        return checkpoint_record(row)

    async def get_checkpoint(
        self, user_id: UUID, project_id: UUID, checkpoint_id: UUID
    ) -> CheckpointRecord:
        row = (
            await self._session.execute(
                select(ProjectCheckpoint).where(
                    ProjectCheckpoint.id == checkpoint_id,
                    ProjectCheckpoint.user_id == user_id,
                    ProjectCheckpoint.project_id == project_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise ProjectRecordNotFoundError()
        return checkpoint_record(row)

    async def list_checkpoints(
        self,
        user_id: UUID,
        project_id: UUID,
        status: RecordStatus | None,
        query: str | None,
        cursor: RecordCursor | None,
        limit: int,
    ) -> list[CheckpointRecord]:
        statement = select(ProjectCheckpoint).where(
            ProjectCheckpoint.user_id == user_id,
            ProjectCheckpoint.project_id == project_id,
        )
        if status is not None:
            statement = statement.where(ProjectCheckpoint.status == status.value)
        if query:
            # Search the bounded snapshot too; parameters are literal text, not SQL patterns.
            statement = statement.where(
                cast(ProjectCheckpoint.payload, Text).icontains(
                    query,
                    autoescape=True,
                )
            )
        if cursor is not None:
            statement = statement.where(
                or_(
                    ProjectCheckpoint.created_at < cursor.created_at,
                    and_(
                        ProjectCheckpoint.created_at == cursor.created_at,
                        ProjectCheckpoint.id < cursor.id,
                    ),
                )
            )
        rows = await self._session.scalars(
            statement.order_by(
                ProjectCheckpoint.created_at.desc(), ProjectCheckpoint.id.desc()
            ).limit(limit)
        )
        return [checkpoint_record(row) for row in rows]

    async def review_checkpoint(
        self,
        user_id: UUID,
        project_id: UUID,
        checkpoint_id: UUID,
        expected_version: int,
        payload: ReviewInput,
    ) -> CheckpointRecord:
        row = (
            await self._session.execute(
                select(ProjectCheckpoint)
                .where(
                    ProjectCheckpoint.id == checkpoint_id,
                    ProjectCheckpoint.user_id == user_id,
                    ProjectCheckpoint.project_id == project_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise ProjectRecordNotFoundError()
        note = (
            payload.contribution_note
            if payload.status == RecordStatus.CONFIRMED
            else row.contribution_note
        )
        if row.status == payload.status and row.contribution_note == note:
            await self._session.commit()
            return checkpoint_record(row)
        if row.version != expected_version or row.status == RecordStatus.WITHDRAWN:
            raise ProjectRecordConflictError()
        if payload.status == RecordStatus.CONFIRMED and row.status != RecordStatus.DRAFT:
            raise ProjectRecordConflictError()
        row.status = payload.status.value
        row.contribution_note = note
        row.version += 1
        row.reviewed_at = datetime.now(UTC)
        await self._session.commit()
        return checkpoint_record(row)


def project_record(row: Project) -> ProjectRecord:
    return ProjectRecord(id=row.id, name=row.name, goal=row.goal, created_at=row.created_at)


def checkpoint_record(row: ProjectCheckpoint) -> CheckpointRecord:
    return CheckpointRecord(
        id=row.id,
        project_id=row.project_id,
        status=RecordStatus(row.status),
        version=row.version,
        payload=CheckpointInput.model_validate(row.payload),
        content_sha256=row.content_sha256,
        contribution_note=row.contribution_note,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )
