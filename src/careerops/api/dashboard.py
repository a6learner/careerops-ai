from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user, get_dashboard_cache
from careerops.db.session import get_session
from careerops.domain.dashboard import DashboardFocus, DashboardSummary, FocusJob
from careerops.domain.users import UserAccount
from careerops.repositories.dashboard import DashboardRepository
from careerops.schemas.dashboard import (
    ActionItemStatusCountsResponse,
    DashboardFocusResponse,
    DashboardSummaryResponse,
    FocusActionItemResponse,
    FocusJobResponse,
    JobStatusCountsResponse,
)
from careerops.services.dashboard import (
    DashboardCache,
    DashboardFocusService,
    DashboardService,
)

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


@router.get("/focus", response_model=DashboardFocusResponse)
async def get_dashboard_focus(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DashboardFocusResponse:
    focus = await DashboardFocusService(DashboardRepository(session)).get_focus(current_user.id)
    return to_focus_response(focus)


def to_focus_response(focus: DashboardFocus) -> DashboardFocusResponse:
    return DashboardFocusResponse(
        generated_at=focus.generated_at,
        today=focus.today,
        upcoming_deadlines=[to_focus_job_response(job) for job in focus.items.upcoming_deadlines],
        recent_jobs=[to_focus_job_response(job) for job in focus.items.recent_jobs],
        open_action_items=[
            FocusActionItemResponse(
                id=item.id,
                job_id=item.job_id,
                job_company=item.job_company,
                job_title=item.job_title,
                title=item.title,
                status=item.status,
                updated_at=item.updated_at,
            )
            for item in focus.items.open_action_items
        ],
    )


def to_focus_job_response(job: FocusJob) -> FocusJobResponse:
    return FocusJobResponse(
        id=job.id,
        company=job.company,
        title=job.title,
        status=job.status,
        deadline=job.deadline,
        updated_at=job.updated_at,
    )


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
