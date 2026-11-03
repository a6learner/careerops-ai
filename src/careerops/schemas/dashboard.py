from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from careerops.domain.action_items import ActionItemStatus
from careerops.domain.jobs import JobStatus


class JobStatusCountsResponse(BaseModel):
    total: int
    saved: int
    preparing: int
    applied: int
    interview: int
    offer: int
    rejected: int
    withdrawn: int


class ActionItemStatusCountsResponse(BaseModel):
    total: int
    todo: int
    doing: int
    done: int


class DashboardSummaryResponse(BaseModel):
    generated_at: datetime
    jobs: JobStatusCountsResponse
    action_items: ActionItemStatusCountsResponse


class FocusJobResponse(BaseModel):
    id: UUID
    company: str
    title: str
    status: JobStatus
    deadline: date | None
    updated_at: datetime


class FocusActionItemResponse(BaseModel):
    id: UUID
    job_id: UUID
    job_company: str
    job_title: str
    title: str
    status: ActionItemStatus
    updated_at: datetime


class DashboardFocusResponse(BaseModel):
    generated_at: datetime
    today: date
    upcoming_deadlines: list[FocusJobResponse]
    recent_jobs: list[FocusJobResponse]
    open_action_items: list[FocusActionItemResponse]
