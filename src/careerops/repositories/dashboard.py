from datetime import date
from uuid import UUID

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import ActionItem, Job
from careerops.domain.action_items import ActionItemStatus
from careerops.domain.dashboard import (
    ActionItemStatusCounts,
    DashboardCounts,
    DashboardFocusItems,
    FocusActionItem,
    FocusJob,
    JobStatusCounts,
)
from careerops.domain.jobs import JobStatus

CLOSED_JOB_STATUSES = (JobStatus.REJECTED.value, JobStatus.WITHDRAWN.value)


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_counts(self, user_id: UUID) -> DashboardCounts:
        job_counts = (
            select(
                literal("job").label("resource_type"),
                Job.status.label("status"),
                func.count().label("item_count"),
            )
            .where(Job.user_id == user_id, Job.deleted_at.is_(None))
            .group_by(Job.status)
        )
        action_item_counts = (
            select(
                literal("action_item").label("resource_type"),
                ActionItem.status.label("status"),
                func.count().label("item_count"),
            )
            .join(Job, Job.id == ActionItem.job_id)
            .where(
                ActionItem.user_id == user_id,
                Job.user_id == user_id,
                Job.deleted_at.is_(None),
            )
            .group_by(ActionItem.status)
        )
        result = await self._session.execute(union_all(job_counts, action_item_counts))

        jobs = {status: 0 for status in JobStatus}
        action_items = {status: 0 for status in ActionItemStatus}
        for resource_type, status, item_count in result.all():
            if resource_type == "job":
                jobs[JobStatus(status)] = int(item_count)
            else:
                action_items[ActionItemStatus(status)] = int(item_count)

        return DashboardCounts(
            jobs=JobStatusCounts(
                total=sum(jobs.values()),
                saved=jobs[JobStatus.SAVED],
                preparing=jobs[JobStatus.PREPARING],
                applied=jobs[JobStatus.APPLIED],
                interview=jobs[JobStatus.INTERVIEW],
                offer=jobs[JobStatus.OFFER],
                rejected=jobs[JobStatus.REJECTED],
                withdrawn=jobs[JobStatus.WITHDRAWN],
            ),
            action_items=ActionItemStatusCounts(
                total=sum(action_items.values()),
                todo=action_items[ActionItemStatus.TODO],
                doing=action_items[ActionItemStatus.DOING],
                done=action_items[ActionItemStatus.DONE],
            ),
        )

    async def get_focus_items(self, user_id: UUID, today: date, limit: int) -> DashboardFocusItems:
        active_jobs = (Job.user_id == user_id, Job.deleted_at.is_(None))
        deadlines = await self._session.execute(
            select(Job)
            .where(
                *active_jobs,
                Job.deadline >= today,
                Job.status.not_in(CLOSED_JOB_STATUSES),
            )
            .order_by(Job.deadline.asc(), Job.id.asc())
            .limit(limit)
        )
        recent = await self._session.execute(
            select(Job)
            .where(*active_jobs)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(limit)
        )
        open_items = await self._session.execute(
            select(ActionItem, Job.company, Job.title)
            .join(Job, Job.id == ActionItem.job_id)
            .where(
                ActionItem.user_id == user_id,
                *active_jobs,
                ActionItem.status != ActionItemStatus.DONE.value,
            )
            .order_by(
                (ActionItem.status == ActionItemStatus.DOING.value).desc(),
                ActionItem.updated_at.desc(),
                ActionItem.id.desc(),
            )
            .limit(limit)
        )
        return DashboardFocusItems(
            upcoming_deadlines=tuple(to_focus_job(job) for job in deadlines.scalars().all()),
            recent_jobs=tuple(to_focus_job(job) for job in recent.scalars().all()),
            open_action_items=tuple(
                FocusActionItem(
                    id=item.id,
                    job_id=item.job_id,
                    job_company=company,
                    job_title=title,
                    title=item.title,
                    status=ActionItemStatus(item.status),
                    updated_at=item.updated_at,
                )
                for item, company, title in open_items.all()
            ),
        )


def to_focus_job(job: Job) -> FocusJob:
    return FocusJob(
        id=job.id,
        company=job.company,
        title=job.title,
        status=JobStatus(job.status),
        deadline=job.deadline,
        updated_at=job.updated_at,
    )
