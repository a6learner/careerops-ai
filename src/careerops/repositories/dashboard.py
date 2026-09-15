from uuid import UUID

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.models import ActionItem, Job
from careerops.domain.action_items import ActionItemStatus
from careerops.domain.dashboard import ActionItemStatusCounts, DashboardCounts, JobStatusCounts
from careerops.domain.jobs import JobStatus


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
