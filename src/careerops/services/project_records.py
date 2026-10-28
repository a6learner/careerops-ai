import base64
import binascii
import hashlib
import json
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ValidationError

from careerops.domain.errors import InvalidCursorError
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointPage,
    CheckpointRecord,
    ProjectInput,
    ProjectPage,
    ProjectRecord,
    RecordCursor,
    RecordStatus,
    ReviewInput,
)


class ProjectRecordStore(Protocol):
    async def create_project(
        self, user_id: UUID, key: str, fingerprint: str, payload: ProjectInput
    ) -> ProjectRecord: ...
    async def get_project(self, user_id: UUID, project_id: UUID) -> ProjectRecord: ...
    async def list_projects(
        self, user_id: UUID, cursor: RecordCursor | None, limit: int
    ) -> list[ProjectRecord]: ...
    async def create_checkpoint(
        self,
        user_id: UUID,
        project_id: UUID,
        key: str,
        fingerprint: str,
        payload: CheckpointInput,
    ) -> CheckpointRecord: ...
    async def get_checkpoint(
        self, user_id: UUID, project_id: UUID, checkpoint_id: UUID
    ) -> CheckpointRecord: ...
    async def list_checkpoints(
        self,
        user_id: UUID,
        project_id: UUID,
        status: RecordStatus | None,
        query: str | None,
        cursor: RecordCursor | None,
        limit: int,
    ) -> list[CheckpointRecord]: ...
    async def review_checkpoint(
        self,
        user_id: UUID,
        project_id: UUID,
        checkpoint_id: UUID,
        expected_version: int,
        payload: ReviewInput,
    ) -> CheckpointRecord: ...


class ProjectRecordService:
    def __init__(self, store: ProjectRecordStore) -> None:
        self._store = store

    async def create_project(self, user_id: UUID, key: str, payload: ProjectInput) -> ProjectRecord:
        return await self._store.create_project(user_id, key, content_hash(payload), payload)

    async def get_project(self, user_id: UUID, project_id: UUID) -> ProjectRecord:
        return await self._store.get_project(user_id, project_id)

    async def list_projects(self, user_id: UUID, cursor: str | None, limit: int) -> ProjectPage:
        rows = await self._store.list_projects(user_id, decode_cursor(cursor), limit + 1)
        page = rows[:limit]
        return ProjectPage(items=page, next_cursor=next_cursor(page, len(rows), limit))

    async def create_checkpoint(
        self, user_id: UUID, project_id: UUID, key: str, payload: CheckpointInput
    ) -> CheckpointRecord:
        await self._store.get_project(user_id, project_id)
        return await self._store.create_checkpoint(
            user_id,
            project_id,
            key,
            content_hash(payload),
            payload,
        )

    async def get_checkpoint(
        self, user_id: UUID, project_id: UUID, checkpoint_id: UUID
    ) -> CheckpointRecord:
        return await self._store.get_checkpoint(user_id, project_id, checkpoint_id)

    async def list_checkpoints(
        self,
        user_id: UUID,
        project_id: UUID,
        status: RecordStatus | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> CheckpointPage:
        await self._store.get_project(user_id, project_id)
        rows = await self._store.list_checkpoints(
            user_id,
            project_id,
            status,
            query,
            decode_cursor(cursor),
            limit + 1,
        )
        page = rows[:limit]
        return CheckpointPage(items=page, next_cursor=next_cursor(page, len(rows), limit))

    async def review_checkpoint(
        self,
        user_id: UUID,
        project_id: UUID,
        checkpoint_id: UUID,
        expected_version: int,
        payload: ReviewInput,
    ) -> CheckpointRecord:
        return await self._store.review_checkpoint(
            user_id,
            project_id,
            checkpoint_id,
            expected_version,
            payload,
        )


def content_hash(payload: BaseModel) -> str:
    raw = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def decode_cursor(value: str | None) -> RecordCursor | None:
    if value is None:
        return None
    try:
        raw = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
        return RecordCursor.model_validate_json(raw)
    except (ValueError, UnicodeError, binascii.Error, ValidationError) as exc:
        raise InvalidCursorError() from exc


def next_cursor(
    page: list[ProjectRecord] | list[CheckpointRecord], row_count: int, limit: int
) -> str | None:
    if not page or row_count <= limit:
        return None
    last = page[-1]
    payload = RecordCursor(created_at=last.created_at, id=last.id)
    return base64.urlsafe_b64encode(payload.model_dump_json().encode("utf-8")).decode("ascii")
