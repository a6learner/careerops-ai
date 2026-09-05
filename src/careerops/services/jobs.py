import base64
import hashlib
import json
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import InvalidCursorError, JobNotFoundError, JobVersionConflictError
from careerops.domain.jobs import JobCreate, JobCursor, JobRecord, JobStatus, JobUpdate


class JobStore(Protocol):
    async def create_job(self, payload: JobCreate, description_hash: str) -> JobRecord: ...

    async def list_jobs(
        self,
        user_id: UUID,
        status: JobStatus | None,
        cursor: JobCursor | None,
        limit: int,
    ) -> list[JobRecord]: ...

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None: ...

    async def update_job(
        self,
        user_id: UUID,
        job_id: UUID,
        expected_version: int,
        payload: JobUpdate,
        description_hash: str,
    ) -> JobRecord | None: ...

    async def soft_delete_job(self, user_id: UUID, job_id: UUID) -> bool: ...

    async def commit(self) -> None: ...


class JobService:
    def __init__(self, jobs: JobStore) -> None:
        self._jobs = jobs

    async def create_job(self, payload: JobCreate) -> JobRecord:
        description_hash = compute_description_hash(payload.raw_description)
        job = await self._jobs.create_job(payload, description_hash)
        await self._jobs.commit()
        return job

    async def list_jobs(
        self,
        user_id: UUID,
        status: JobStatus | None,
        cursor: JobCursor | None,
        limit: int,
    ) -> tuple[list[JobRecord], str | None]:
        rows = await self._jobs.list_jobs(
            user_id=user_id,
            status=status,
            cursor=cursor,
            limit=limit + 1,
        )
        page = rows[:limit]
        next_cursor = encode_job_cursor(page[-1]) if len(rows) > limit and page else None
        return page, next_cursor

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord:
        job = await self._jobs.get_job(user_id, job_id)
        if job is None:
            raise JobNotFoundError()
        return job

    async def update_job(
        self,
        user_id: UUID,
        job_id: UUID,
        expected_version: int,
        payload: JobUpdate,
    ) -> JobRecord:
        current = await self.get_job(user_id, job_id)
        if current.version != expected_version:
            raise JobVersionConflictError(current.version)

        merged = merge_job(current, payload)
        description_hash = compute_description_hash(merged.raw_description)
        updated = await self._jobs.update_job(
            user_id=user_id,
            job_id=job_id,
            expected_version=expected_version,
            payload=payload,
            description_hash=description_hash,
        )
        if updated is None:
            raise JobVersionConflictError(current.version)
        await self._jobs.commit()
        return updated

    async def delete_job(self, user_id: UUID, job_id: UUID) -> None:
        deleted = await self._jobs.soft_delete_job(user_id, job_id)
        if not deleted:
            raise JobNotFoundError()
        await self._jobs.commit()


def compute_description_hash(raw_description: str) -> str:
    normalized = " ".join(raw_description.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def encode_job_cursor(job: JobRecord) -> str:
    payload = {
        "updated_at": job.updated_at.isoformat(),
        "id": str(job.id),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_job_cursor(value: str | None) -> JobCursor | None:
    if value is None:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        payload = json.loads(decoded)
        if not isinstance(payload, dict):
            raise InvalidCursorError()
        updated_at = payload.get("updated_at")
        job_id = payload.get("id")
        if not isinstance(updated_at, str) or not isinstance(job_id, str):
            raise InvalidCursorError()
        return JobCursor(updated_at=datetime.fromisoformat(updated_at), id=UUID(job_id))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidCursorError() from exc


def merge_job(current: JobRecord, update: JobUpdate) -> JobRecord:
    source_url = current.source_url
    if update.clear_source_url:
        source_url = None
    elif update.source_url is not None:
        source_url = update.source_url

    location = current.location
    if update.clear_location:
        location = None
    elif update.location is not None:
        location = update.location

    deadline = current.deadline
    if update.clear_deadline:
        deadline = None
    elif update.deadline is not None:
        deadline = update.deadline

    return JobRecord(
        id=current.id,
        user_id=current.user_id,
        company=update.company if update.company is not None else current.company,
        title=update.title if update.title is not None else current.title,
        raw_description=update.raw_description
        if update.raw_description is not None
        else current.raw_description,
        description_hash=current.description_hash,
        source_url=source_url,
        location=location,
        deadline=deadline,
        status=update.status if update.status is not None else current.status,
        version=current.version,
        created_at=current.created_at,
        updated_at=current.updated_at,
    )
