from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from careerops.domain.action_items import ActionItemStatus
from careerops.domain.jobs import JobStatus


@dataclass(frozen=True)
class JobStatusCounts:
    total: int
    saved: int
    preparing: int
    applied: int
    interview: int
    offer: int
    rejected: int
    withdrawn: int


@dataclass(frozen=True)
class ActionItemStatusCounts:
    total: int
    todo: int
    doing: int
    done: int


@dataclass(frozen=True)
class DashboardCounts:
    jobs: JobStatusCounts
    action_items: ActionItemStatusCounts


@dataclass(frozen=True)
class DashboardSummary:
    generated_at: datetime
    jobs: JobStatusCounts
    action_items: ActionItemStatusCounts


@dataclass(frozen=True)
class FocusJob:
    id: UUID
    company: str
    title: str
    status: JobStatus
    deadline: date | None
    updated_at: datetime


@dataclass(frozen=True)
class FocusActionItem:
    id: UUID
    job_id: UUID
    job_company: str
    job_title: str
    title: str
    status: ActionItemStatus
    updated_at: datetime


@dataclass(frozen=True)
class DashboardFocusItems:
    upcoming_deadlines: tuple[FocusJob, ...]
    recent_jobs: tuple[FocusJob, ...]
    open_action_items: tuple[FocusActionItem, ...]


@dataclass(frozen=True)
class DashboardFocus:
    generated_at: datetime
    today: date
    items: DashboardFocusItems
