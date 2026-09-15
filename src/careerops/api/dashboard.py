from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user, get_dashboard_cache
from careerops.db.session import get_session
from careerops.domain.dashboard import DashboardSummary
from careerops.domain.users import UserAccount
from careerops.repositories.dashboard import DashboardRepository
from careerops.schemas.dashboard import (
    ActionItemStatusCountsResponse,
    DashboardSummaryResponse,
    JobStatusCountsResponse,
)
from careerops.services.dashboard import DashboardCache, DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
) -> DashboardSummaryResponse:
    summary = await DashboardService(DashboardRepository(session), cache).get_summary(
        current_user.id
    )
    return to_response(summary)


def to_response(summary: DashboardSummary) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        generated_at=summary.generated_at,
        jobs=JobStatusCountsResponse(
            total=summary.jobs.total,
            saved=summary.jobs.saved,
            preparing=summary.jobs.preparing,
            applied=summary.jobs.applied,
            interview=summary.jobs.interview,
            offer=summary.jobs.offer,
            rejected=summary.jobs.rejected,
            withdrawn=summary.jobs.withdrawn,
        ),
        action_items=ActionItemStatusCountsResponse(
            total=summary.action_items.total,
            todo=summary.action_items.todo,
            doing=summary.action_items.doing,
            done=summary.action_items.done,
        ),
    )
