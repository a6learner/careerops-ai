from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import InvalidCursorError, JobNotFoundError, JobVersionConflictError
from careerops.domain.jobs import JobCreate, JobCursor, JobRecord, JobStatus, JobUpdate
from careerops.services.jobs import (
    JobService,
    compute_description_hash,
    decode_job_cursor,
    encode_job_cursor,
)


class InMemoryJobStore:
    def __init__(self, existing: list[JobRecord] | None = None) -> None:
        self.existing = existing or []
        self.created_hash: str | None = None
        self.updated_hash: str | None = None
        self.committed = False
        self.deleted = False

    async def create_job(self, payload: JobCreate, description_hash: str) -> JobRecord:
        self.created_hash = description_hash
        now = datetime.now(UTC)
        return JobRecord(
            id=uuid4(),
            user_id=payload.user_id,
            company=payload.company,
            title=payload.title,
            raw_description=payload.raw_description,
            description_hash=description_hash,
            source_url=payload.source_url,
            location=payload.location,
            deadline=payload.deadline,
            status=payload.status,
            version=1,
            created_at=now,
            updated_at=now,
        )

    async def list_jobs(
        self,
        user_id: UUID,
        status: JobStatus | None,
        cursor: JobCursor | None,
        limit: int,
    ) -> list[JobRecord]:
        rows = [job for job in self.existing if job.user_id == user_id]
        if status is not None:
            rows = [job for job in rows if job.status == status]
        if cursor is not None:
            rows = [
                job
                for job in rows
                if job.updated_at < cursor.updated_at
                or (job.updated_at == cursor.updated_at and job.id < cursor.id)
            ]
        return rows[:limit]

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None:
        for job in self.existing:
            if job.user_id == user_id and job.id == job_id:
                return job
        return None

    async def update_job(
        self,
        user_id: UUID,
        job_id: UUID,
        expected_version: int,
        payload: JobUpdate,
        description_hash: str,
    ) -> JobRecord | None:
        self.updated_hash = description_hash
        current = await self.get_job(user_id, job_id)
        if current is None or current.version != expected_version:
            return None
        return JobRecord(
            id=job_id,
            user_id=user_id,
            company=payload.company or current.company,
            title=payload.title or current.title,
            raw_description=payload.raw_description or current.raw_description,
            description_hash=description_hash,
            source_url=(
                None if payload.clear_source_url else payload.source_url or current.source_url
            ),
            location=None if payload.clear_location else payload.location or current.location,
            deadline=None if payload.clear_deadline else payload.deadline or current.deadline,
            status=payload.status or current.status,
            version=expected_version + 1,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )

    async def soft_delete_job(self, user_id: UUID, job_id: UUID) -> bool:
        self.deleted = await self.get_job(user_id, job_id) is not None
        return self.deleted

    async def commit(self) -> None:
        self.committed = True


def make_create(user_id: UUID, raw_description: str = "Build reliable APIs.") -> JobCreate:
    return JobCreate(
        user_id=user_id,
        company="OpenAI",
        title="Backend Engineer Intern",
        raw_description=raw_description,
        source_url=None,
        location=None,
        deadline=None,
    )


def make_record(user_id: UUID, updated_at: datetime | None = None) -> JobRecord:
    now = updated_at or datetime.now(UTC)
    payload = make_create(user_id)
    return JobRecord(
        id=uuid4(),
        user_id=user_id,
        company=payload.company,
        title=payload.title,
        raw_description=payload.raw_description,
        description_hash=compute_description_hash(payload.raw_description),
        source_url=payload.source_url,
        location=payload.location,
        deadline=payload.deadline,
        status=payload.status,
        version=2,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_job_computes_description_hash_and_commits() -> None:
    store = InMemoryJobStore()
    service = JobService(store)
    payload = make_create(uuid4(), raw_description=" Build   reliable APIs. ")

    job = await service.create_job(payload)

    assert job.description_hash == compute_description_hash("Build reliable APIs.")
    assert store.created_hash == job.description_hash
    assert store.committed


@pytest.mark.asyncio
async def test_list_jobs_returns_next_cursor_when_more_rows_exist() -> None:
    user_id = uuid4()
    first = make_record(user_id, datetime(2026, 9, 4, 12, 0, tzinfo=UTC))
    second = make_record(user_id, datetime(2026, 9, 4, 11, 0, tzinfo=UTC))
    service = JobService(InMemoryJobStore([first, second]))

    jobs, next_cursor = await service.list_jobs(user_id, status=None, cursor=None, limit=1)

    assert jobs == [first]
    assert next_cursor == encode_job_cursor(first)


def test_job_cursor_round_trips() -> None:
    job = make_record(uuid4(), datetime(2026, 9, 4, 12, 0, tzinfo=UTC))

    cursor = decode_job_cursor(encode_job_cursor(job))

    assert cursor == JobCursor(updated_at=job.updated_at, id=job.id)


@pytest.mark.asyncio
async def test_job_cursor_tie_breaks_on_id_when_updated_at_matches() -> None:
    user_id = uuid4()
    timestamp = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    first = make_record(user_id, timestamp)
    second = make_record(user_id, timestamp)
    ordered = sorted([first, second], key=lambda job: job.id, reverse=True)
    service = JobService(InMemoryJobStore(ordered))

    jobs, _ = await service.list_jobs(
        user_id,
        status=None,
        cursor=JobCursor(updated_at=ordered[0].updated_at, id=ordered[0].id),
        limit=10,
    )

    assert jobs == [ordered[1]]


def test_invalid_job_cursor_raises_domain_error() -> None:
    with pytest.raises(InvalidCursorError):
        decode_job_cursor("not-a-cursor")


@pytest.mark.asyncio
async def test_get_job_raises_not_found_when_store_returns_none() -> None:
    service = JobService(InMemoryJobStore())

    with pytest.raises(JobNotFoundError):
        await service.get_job(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_update_job_rejects_stale_version() -> None:
    user_id = uuid4()
    existing = make_record(user_id)
    service = JobService(InMemoryJobStore([existing]))

    with pytest.raises(JobVersionConflictError):
        await service.update_job(
            user_id=user_id,
            job_id=existing.id,
            expected_version=1,
            payload=JobUpdate(title="Updated title"),
        )


@pytest.mark.asyncio
async def test_delete_job_commits_soft_delete() -> None:
    user_id = uuid4()
    existing = make_record(user_id)
    store = InMemoryJobStore([existing])
    service = JobService(store)

    await service.delete_job(user_id, existing.id)

    assert store.deleted
    assert store.committed
