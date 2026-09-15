from dataclasses import dataclass
from datetime import datetime


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
