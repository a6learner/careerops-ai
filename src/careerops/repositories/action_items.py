from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import ActionItem, AnalysisRun, EvidenceMatch, Job
from careerops.domain.action_items import (
    ActionItemCreate,
    ActionItemCreationResult,
    ActionItemCursor,
    ActionItemRecord,
    ActionItemSourceRecord,
    ActionItemStatus,
    ActionItemUpdate,
)
from careerops.domain.analysis_runs import AnalysisRunStatus
from careerops.domain.evidence_matching import EvidenceVerdict


class ActionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> ActionItemRecord | None:
        result = await self._session.execute(
            select(ActionItem, Job.deleted_at)
            .join(Job, Job.id == ActionItem.job_id)
            .where(
                ActionItem.user_id == user_id,
                ActionItem.idempotency_key == idempotency_key,
            )
        )
        row = result.one_or_none()
        return None if row is None else to_record(row[0], row[1])

    async def get_source(
        self,
        user_id: UUID,
        job_id: UUID,
        evidence_match_id: UUID,
    ) -> ActionItemSourceRecord | None:
        result = await self._session.execute(
            select(EvidenceMatch.id, EvidenceMatch.verdict)
            .join(AnalysisRun, AnalysisRun.id == EvidenceMatch.analysis_run_id)
            .where(
                EvidenceMatch.id == evidence_match_id,
                AnalysisRun.user_id == user_id,
                AnalysisRun.job_id == job_id,
                AnalysisRun.status == AnalysisRunStatus.SUCCEEDED.value,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return ActionItemSourceRecord(id=row.id, verdict=EvidenceVerdict(row.verdict))

    async def create_or_get(
        self,
        payload: ActionItemCreate,
        request_fingerprint: str,
    ) -> ActionItemCreationResult:
        item_id = uuid4()
        result = await self._session.execute(
            insert(ActionItem)
            .values(
                id=item_id,
                user_id=payload.user_id,
                job_id=payload.job_id,
                source_evidence_match_id=payload.source_evidence_match_id,
                title=payload.title,
                status=ActionItemStatus.TODO.value,
                version=1,
                idempotency_key=payload.idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            .on_conflict_do_nothing(index_elements=[ActionItem.user_id, ActionItem.idempotency_key])
            .returning(ActionItem.id)
        )
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            existing = await self.get_by_idempotency_key(
                payload.user_id,
                payload.idempotency_key,
            )
            if existing is None:
                raise RuntimeError("Action item conflict did not resolve to an existing item.")
            return ActionItemCreationResult(item=existing, created=False)

        created = await self.get_action_item(payload.user_id, item_id)
        if created is None:
            raise RuntimeError("Inserted action item could not be loaded.")
        return ActionItemCreationResult(item=created, created=True)

    async def list_action_items(
        self,
        user_id: UUID,
        status: ActionItemStatus | None,
        job_id: UUID | None,
        cursor: ActionItemCursor | None,
        limit: int,
    ) -> list[ActionItemRecord]:
        conditions = [ActionItem.user_id == user_id]
        if status is not None:
            conditions.append(ActionItem.status == status.value)
        if job_id is not None:
            conditions.append(ActionItem.job_id == job_id)
        if cursor is not None:
            conditions.append(
                or_(
                    ActionItem.updated_at < cursor.updated_at,
                    and_(
                        ActionItem.updated_at == cursor.updated_at,
                        ActionItem.id < cursor.id,
                    ),
                )
            )

        result = await self._session.execute(
            select(ActionItem, Job.deleted_at)
            .join(Job, Job.id == ActionItem.job_id)
            .where(*conditions)
            .order_by(ActionItem.updated_at.desc(), ActionItem.id.desc())
            .limit(limit)
        )
        return [to_record(item, deleted_at) for item, deleted_at in result.all()]

    async def get_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
    ) -> ActionItemRecord | None:
        result = await self._session.execute(
            select(ActionItem, Job.deleted_at)
            .join(Job, Job.id == ActionItem.job_id)
            .where(
                ActionItem.id == action_item_id,
                ActionItem.user_id == user_id,
            )
        )
        row = result.one_or_none()
        return None if row is None else to_record(row[0], row[1])

    async def update_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
        expected_version: int,
        payload: ActionItemUpdate,
    ) -> ActionItemRecord | None:
        values: dict[str, object] = {
            "version": expected_version + 1,
            "updated_at": datetime.now(UTC),
        }
        if payload.title is not None:
            values["title"] = payload.title
        if payload.status is not None:
            values["status"] = payload.status.value

        result = await self._session.execute(
            update(ActionItem)
            .where(
                ActionItem.id == action_item_id,
                ActionItem.user_id == user_id,
                ActionItem.version == expected_version,
            )
            .values(**values)
            .returning(ActionItem.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        return await self.get_action_item(user_id, action_item_id)

    async def commit(self) -> None:
        await self._session.commit()


def to_record(item: ActionItem, job_deleted_at: datetime | None) -> ActionItemRecord:
    return ActionItemRecord(
        id=item.id,
        user_id=item.user_id,
        job_id=item.job_id,
        source_evidence_match_id=item.source_evidence_match_id,
        title=item.title,
        status=ActionItemStatus(item.status),
        version=item.version,
        idempotency_key=item.idempotency_key,
        request_fingerprint=item.request_fingerprint,
        job_is_archived=job_deleted_at is not None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
