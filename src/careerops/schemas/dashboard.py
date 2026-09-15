from datetime import datetime

from pydantic import BaseModel


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
