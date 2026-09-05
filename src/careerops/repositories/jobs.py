from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import Job
from careerops.domain.jobs import JobCreate, JobCursor, JobRecord, JobStatus, JobUpdate


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(self, payload: JobCreate, description_hash: str) -> JobRecord:
        job = Job(
            user_id=payload.user_id,
            company=payload.company,
            title=payload.title,
            raw_description=payload.raw_description,
            description_hash=description_hash,
            source_url=payload.source_url,
            location=payload.location,
            deadline=payload.deadline,
            status=payload.status.value,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return to_record(job)

    async def list_jobs(
        self,
        user_id: UUID,
        status: JobStatus | None,
        cursor: JobCursor | None,
        limit: int,
    ) -> list[JobRecord]:
        conditions = [Job.user_id == user_id, Job.deleted_at.is_(None)]
        if status is not None:
            conditions.append(Job.status == status.value)
        if cursor is not None:
            conditions.append(
                or_(
                    Job.updated_at < cursor.updated_at,
                    and_(Job.updated_at == cursor.updated_at, Job.id < cursor.id),
                )
            )

        result = await self._session.execute(
            select(Job)
            .where(*conditions)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(limit)
        )
        return [to_record(job) for job in result.scalars().all()]

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None:
        result = await self._session.execute(
            select(Job).where(
                Job.id == job_id,
                Job.user_id == user_id,
                Job.deleted_at.is_(None),
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        return to_record(job)

    async def update_job(
        self,
        user_id: UUID,
        job_id: UUID,
        expected_version: int,
        payload: JobUpdate,
        description_hash: str,
    ) -> JobRecord | None:
        values: dict[str, object] = {
            "version": expected_version + 1,
            "description_hash": description_hash,
            "updated_at": datetime.now(UTC),
        }
        if payload.company is not None:
            values["company"] = payload.company
        if payload.title is not None:
            values["title"] = payload.title
        if payload.raw_description is not None:
            values["raw_description"] = payload.raw_description
        if payload.clear_source_url:
            values["source_url"] = None
        elif payload.source_url is not None:
            values["source_url"] = payload.source_url
        if payload.clear_location:
            values["location"] = None
        elif payload.location is not None:
            values["location"] = payload.location
        if payload.clear_deadline:
            values["deadline"] = None
        elif payload.deadline is not None:
            values["deadline"] = payload.deadline
        if payload.status is not None:
            values["status"] = payload.status.value

        result = await self._session.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.user_id == user_id,
                Job.deleted_at.is_(None),
                Job.version == expected_version,
            )
            .values(**values)
            .returning(Job)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        return to_record(job)

    async def soft_delete_job(self, user_id: UUID, job_id: UUID) -> bool:
        result = await self._session.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.user_id == user_id,
                Job.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC), updated_at=datetime.now(UTC))
            .returning(Job.id)
        )
        return result.scalar_one_or_none() is not None

    async def commit(self) -> None:
        await self._session.commit()


def to_record(job: Job) -> JobRecord:
    return JobRecord(
        id=job.id,
        user_id=job.user_id,
        company=job.company,
        title=job.title,
        raw_description=job.raw_description,
        description_hash=job.description_hash,
        source_url=job.source_url,
        location=job.location,
        deadline=job.deadline,
        status=JobStatus(job.status),
        version=job.version,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
