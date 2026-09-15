import base64
import hashlib
import json
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.action_items import (
    ActionItemCreate,
    ActionItemCreationResult,
    ActionItemCursor,
    ActionItemRecord,
    ActionItemSourceRecord,
    ActionItemStatus,
    ActionItemUpdate,
)
from careerops.domain.errors import (
    ActionItemNotFoundError,
    ActionItemSourceNotActionableError,
    ActionItemSourceNotFoundError,
    ActionItemVersionConflictError,
    IdempotencyKeyConflictError,
    InvalidCursorError,
    JobNotFoundError,
)
from careerops.domain.evidence_matching import EvidenceVerdict
from careerops.domain.jobs import JobRecord
from careerops.services.dashboard import DashboardCacheInvalidator

ACTIONABLE_VERDICTS = frozenset(
    {
        EvidenceVerdict.PARTIAL,
        EvidenceVerdict.MISSING,
        EvidenceVerdict.INSUFFICIENT_EVIDENCE,
    }
)


class ActionItemJobReader(Protocol):
    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None: ...


class ActionItemStore(Protocol):
    async def get_by_idempotency_key(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> ActionItemRecord | None: ...

    async def get_source(
        self,
        user_id: UUID,
        job_id: UUID,
        evidence_match_id: UUID,
    ) -> ActionItemSourceRecord | None: ...

    async def create_or_get(
        self,
        payload: ActionItemCreate,
        request_fingerprint: str,
    ) -> ActionItemCreationResult: ...

    async def list_action_items(
        self,
        user_id: UUID,
        status: ActionItemStatus | None,
        job_id: UUID | None,
        cursor: ActionItemCursor | None,
        limit: int,
    ) -> list[ActionItemRecord]: ...

    async def get_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
    ) -> ActionItemRecord | None: ...

    async def update_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
        expected_version: int,
        payload: ActionItemUpdate,
    ) -> ActionItemRecord | None: ...

    async def commit(self) -> None: ...


class ActionItemService:
    def __init__(
        self,
        jobs: ActionItemJobReader,
        action_items: ActionItemStore,
        dashboard_cache: DashboardCacheInvalidator,
    ) -> None:
        self._jobs = jobs
        self._action_items = action_items
        self._dashboard_cache = dashboard_cache

    async def create_action_item(self, payload: ActionItemCreate) -> ActionItemRecord:
        request_fingerprint = compute_action_item_request_fingerprint(payload)
        existing = await self._action_items.get_by_idempotency_key(
            payload.user_id,
            payload.idempotency_key,
        )
        if existing is not None:
            ensure_matching_action_item_request(existing, request_fingerprint)
            return existing

        if await self._jobs.get_job(payload.user_id, payload.job_id) is None:
            raise JobNotFoundError()

        if payload.source_evidence_match_id is not None:
            source = await self._action_items.get_source(
                payload.user_id,
                payload.job_id,
                payload.source_evidence_match_id,
            )
            if source is None:
                raise ActionItemSourceNotFoundError()
            if source.verdict not in ACTIONABLE_VERDICTS:
                raise ActionItemSourceNotActionableError()

        creation = await self._action_items.create_or_get(payload, request_fingerprint)
        ensure_matching_action_item_request(creation.item, request_fingerprint)
        if creation.created:
            await self._action_items.commit()
            await self._dashboard_cache.invalidate(payload.user_id)
        return creation.item

    async def list_action_items(
        self,
        user_id: UUID,
        status: ActionItemStatus | None,
        job_id: UUID | None,
        cursor: ActionItemCursor | None,
        limit: int,
    ) -> tuple[list[ActionItemRecord], str | None]:
        rows = await self._action_items.list_action_items(
            user_id=user_id,
            status=status,
            job_id=job_id,
            cursor=cursor,
            limit=limit + 1,
        )
        page = rows[:limit]
        next_cursor = encode_action_item_cursor(page[-1]) if len(rows) > limit and page else None
        return page, next_cursor

    async def update_action_item(
        self,
        user_id: UUID,
        action_item_id: UUID,
        expected_version: int,
        payload: ActionItemUpdate,
    ) -> ActionItemRecord:
        current = await self._action_items.get_action_item(user_id, action_item_id)
        if current is None:
            raise ActionItemNotFoundError()
        if current.version != expected_version:
            raise ActionItemVersionConflictError(current.version)

        updated = await self._action_items.update_action_item(
            user_id,
            action_item_id,
            expected_version,
            payload,
        )
        if updated is None:
            raise ActionItemVersionConflictError(current.version)
        await self._action_items.commit()
        await self._dashboard_cache.invalidate(user_id)
        return updated


def compute_action_item_request_fingerprint(payload: ActionItemCreate) -> str:
    serialized = json.dumps(
        {
            "job_id": str(payload.job_id),
            "source_evidence_match_id": (
                None
                if payload.source_evidence_match_id is None
                else str(payload.source_evidence_match_id)
            ),
            "title": payload.title,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def ensure_matching_action_item_request(
    item: ActionItemRecord,
    request_fingerprint: str,
) -> None:
    if item.request_fingerprint != request_fingerprint:
        raise IdempotencyKeyConflictError()


def encode_action_item_cursor(item: ActionItemRecord) -> str:
    payload = {"updated_at": item.updated_at.isoformat(), "id": str(item.id)}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_action_item_cursor(value: str | None) -> ActionItemCursor | None:
    if value is None:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        payload = json.loads(decoded)
        if not isinstance(payload, dict):
            raise InvalidCursorError()
        updated_at = payload.get("updated_at")
        action_item_id = payload.get("id")
        if not isinstance(updated_at, str) or not isinstance(action_item_id, str):
            raise InvalidCursorError()
        return ActionItemCursor(
            updated_at=datetime.fromisoformat(updated_at),
            id=UUID(action_item_id),
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidCursorError() from exc
