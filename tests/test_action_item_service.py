from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.action_items import (
    ActionItemCreate,
    ActionItemCreationResult,
    ActionItemCursor,
    ActionItemRecord,
    ActionItemSourceRecord,
    ActionItemStatus,
    ActionItemUpdate,
)
from careerops.domain.dashboard import DashboardSummary
from careerops.domain.errors import (
    ActionItemSourceNotActionableError,
    ActionItemSourceNotFoundError,
    ActionItemVersionConflictError,
    IdempotencyKeyConflictError,
    JobNotFoundError,
)
from careerops.domain.evidence_matching import EvidenceVerdict
from careerops.domain.jobs import JobRecord, JobStatus
from careerops.services.action_items import (
    ActionItemService,
    compute_action_item_request_fingerprint,
    decode_action_item_cursor,
    encode_action_item_cursor,
)


class InMemoryJobReader:
    def __init__(self, active_job_ids: set[UUID]) -> None:
        self.active_job_ids = active_job_ids

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None:
        if job_id not in self.active_job_ids:
            return None
        now = datetime.now(UTC)
        return JobRecord(
            id=job_id,
            user_id=user_id,
            company="Example",
            title="Backend Intern",
            raw_description="Build APIs.",
            description_hash="a" * 64,
            source_url=None,
            location=None,
            deadline=None,
            status=JobStatus.SAVED,
            version=1,
            created_at=now,
            updated_at=now,
        )


class InMemoryActionItemStore:
    def __init__(
        self,
        existing: list[ActionItemRecord] | None = None,
        sources: dict[UUID, ActionItemSourceRecord] | None = None,
    ) -> None:
        self.items = existing or []
        self.sources = sources or {}
        self.committed = False

    async def get_by_idempotency_key(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> ActionItemRecord | None:
        return next(
            (
                item
                for item in self.items
                if item.user_id == user_id and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_source(
        self,
        user_id: UUID,
        job_id: UUID,
        evidence_match_id: UUID,
    ) -> ActionItemSourceRecord | None:
        return self.sources.get(evidence_match_id)

    async def create_or_get(
        self,
        payload: ActionItemCreate,
        request_fingerprint: str,
    ) -> ActionItemCreationResult:
        existing = await self.get_by_idempotency_key(payload.user_id, payload.idempotency_key)
        if existing is not None:
            return ActionItemCreationResult(existing, created=False)
        now = datetime.now(UTC)
        item = ActionItemRecord(
            id=uuid4(),
            user_id=payload.user_id,
            job_id=payload.job_id,
            source_evidence_match_id=payload.source_evidence_match_id,
            title=payload.title,
            status=ActionItemStatus.TODO,
            version=1,
            idempotency_key=payload.idempotency_key,
            request_fingerprint=request_fingerprint,
            job_is_archived=False,
            created_at=now,
            updated_at=now,
        )
        self.items.append(item)
        return ActionItemCreationResult(item, created=True)

    async def list_action_items(
        self,
        user_id: UUID,
        status: ActionItemStatus | None,
        job_id: UUID | None,
        cursor: ActionItemCursor | None,
        limit: int,
    ) -> list[ActionItemRecord]:
        rows = [item for item in self.items if item.user_id == user_id]
        if status is not None:
            rows = [item for item in rows if item.status is status]
        if job_id is not None:
            rows = [item for item in rows if item.job_id == job_id]
        if cursor is not None:
            rows = [
                item
                for item in rows
                if item.updated_at < cursor.updated_at
                or (item.updated_at == cursor.updated_at and item.id < cursor.id)
            ]
        return rows[:limit]

    async def get_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
    ) -> ActionItemRecord | None:
        return next(
            (item for item in self.items if item.user_id == user_id and item.id == action_item_id),
            None,
        )

    async def update_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
        expected_version: int,
        payload: ActionItemUpdate,
    ) -> ActionItemRecord | None:
        current = await self.get_action_item(user_id, action_item_id)
        if current is None or current.version != expected_version:
            return None
        updated = ActionItemRecord(
            id=current.id,
            user_id=current.user_id,
            job_id=current.job_id,
            source_evidence_match_id=current.source_evidence_match_id,
            title=payload.title or current.title,
            status=payload.status or current.status,
            version=current.version + 1,
            idempotency_key=current.idempotency_key,
            request_fingerprint=current.request_fingerprint,
            job_is_archived=current.job_is_archived,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )
        self.items[self.items.index(current)] = updated
        return updated

    async def commit(self) -> None:
        self.committed = True


class InMemoryDashboardCache:
    def __init__(self) -> None:
        self.invalidated_user_ids: list[UUID] = []

    async def get(self, user_id: UUID) -> DashboardSummary | None:
        return None

    async def set(self, user_id: UUID, summary: DashboardSummary) -> None:
        return None

    async def invalidate(self, user_id: UUID) -> None:
        self.invalidated_user_ids.append(user_id)


class FailingCommitActionItemStore(InMemoryActionItemStore):
    async def commit(self) -> None:
        raise RuntimeError("database commit failed")


def make_create(
    user_id: UUID,
    job_id: UUID,
    *,
    key: str = "item-key",
    source_id: UUID | None = None,
    title: str = "Practice system design",
) -> ActionItemCreate:
    return ActionItemCreate(
        user_id=user_id,
        job_id=job_id,
        title=title,
        source_evidence_match_id=source_id,
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_create_manual_action_item_defaults_to_todo_and_commits() -> None:
    user_id = uuid4()
    job_id = uuid4()
    store = InMemoryActionItemStore()

    cache = InMemoryDashboardCache()
    item = await ActionItemService(
        InMemoryJobReader({job_id}), store, cache
    ).create_action_item(make_create(user_id, job_id))

    assert item.status is ActionItemStatus.TODO
    assert item.source_evidence_match_id is None
    assert store.committed
    assert cache.invalidated_user_ids == [user_id]


@pytest.mark.asyncio
async def test_create_action_item_does_not_invalidate_before_commit_succeeds() -> None:
    user_id = uuid4()
    job_id = uuid4()
    cache = InMemoryDashboardCache()

    with pytest.raises(RuntimeError, match="database commit failed"):
        await ActionItemService(
            InMemoryJobReader({job_id}),
            FailingCommitActionItemStore(),
            cache,
        ).create_action_item(make_create(user_id, job_id))

    assert cache.invalidated_user_ids == []


@pytest.mark.parametrize(
    "verdict",
    [
        EvidenceVerdict.PARTIAL,
        EvidenceVerdict.MISSING,
        EvidenceVerdict.INSUFFICIENT_EVIDENCE,
    ],
)
@pytest.mark.asyncio
async def test_create_from_supported_gap_verdict(verdict: EvidenceVerdict) -> None:
    user_id = uuid4()
    job_id = uuid4()
    source_id = uuid4()
    store = InMemoryActionItemStore(sources={source_id: ActionItemSourceRecord(source_id, verdict)})

    item = await ActionItemService(
        InMemoryJobReader({job_id}), store, InMemoryDashboardCache()
    ).create_action_item(make_create(user_id, job_id, source_id=source_id))

    assert item.source_evidence_match_id == source_id


@pytest.mark.asyncio
async def test_create_rejects_matched_or_missing_source() -> None:
    user_id = uuid4()
    job_id = uuid4()
    source_id = uuid4()
    matched_store = InMemoryActionItemStore(
        sources={source_id: ActionItemSourceRecord(source_id, EvidenceVerdict.MATCHED)}
    )

    with pytest.raises(ActionItemSourceNotActionableError):
        await ActionItemService(
            InMemoryJobReader({job_id}), matched_store, InMemoryDashboardCache()
        ).create_action_item(make_create(user_id, job_id, source_id=source_id))
    with pytest.raises(ActionItemSourceNotFoundError):
        await ActionItemService(
            InMemoryJobReader({job_id}), InMemoryActionItemStore(), InMemoryDashboardCache()
        ).create_action_item(make_create(user_id, job_id, source_id=source_id))


@pytest.mark.asyncio
async def test_create_requires_active_owned_job() -> None:
    with pytest.raises(JobNotFoundError):
        await ActionItemService(
            InMemoryJobReader(set()), InMemoryActionItemStore(), InMemoryDashboardCache()
        ).create_action_item(make_create(uuid4(), uuid4()))


@pytest.mark.asyncio
async def test_idempotent_replay_returns_existing_and_changed_request_conflicts() -> None:
    user_id = uuid4()
    job_id = uuid4()
    payload = make_create(user_id, job_id)
    store = InMemoryActionItemStore()
    cache = InMemoryDashboardCache()
    service = ActionItemService(InMemoryJobReader({job_id}), store, cache)
    first = await service.create_action_item(payload)

    replay = await service.create_action_item(payload)

    assert replay.id == first.id
    assert cache.invalidated_user_ids == [user_id]
    with pytest.raises(IdempotencyKeyConflictError):
        await service.create_action_item(make_create(user_id, job_id, title="Different title"))


def test_action_item_cursor_round_trips() -> None:
    payload = make_create(uuid4(), uuid4())
    now = datetime.now(UTC)
    item = ActionItemRecord(
        id=uuid4(),
        user_id=payload.user_id,
        job_id=payload.job_id,
        source_evidence_match_id=None,
        title=payload.title,
        status=ActionItemStatus.TODO,
        version=1,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=compute_action_item_request_fingerprint(payload),
        job_is_archived=False,
        created_at=now,
        updated_at=now,
    )

    assert decode_action_item_cursor(encode_action_item_cursor(item)) == ActionItemCursor(
        item.updated_at,
        item.id,
    )


@pytest.mark.asyncio
async def test_update_allows_archived_job_item_and_rejects_stale_version() -> None:
    user_id = uuid4()
    job_id = uuid4()
    payload = make_create(user_id, job_id)
    now = datetime.now(UTC)
    archived = ActionItemRecord(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        source_evidence_match_id=None,
        title=payload.title,
        status=ActionItemStatus.TODO,
        version=1,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=compute_action_item_request_fingerprint(payload),
        job_is_archived=True,
        created_at=now,
        updated_at=now,
    )
    store = InMemoryActionItemStore([archived])
    cache = InMemoryDashboardCache()
    service = ActionItemService(InMemoryJobReader(set()), store, cache)

    updated = await service.update_action_item(
        user_id,
        archived.id,
        1,
        ActionItemUpdate(status=ActionItemStatus.DONE),
    )

    assert updated.status is ActionItemStatus.DONE
    assert updated.job_is_archived
    assert cache.invalidated_user_ids == [user_id]
    with pytest.raises(ActionItemVersionConflictError):
        await service.update_action_item(
            user_id,
            archived.id,
            1,
            ActionItemUpdate(status=ActionItemStatus.DOING),
        )
