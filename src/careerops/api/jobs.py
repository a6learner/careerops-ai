from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.api.preconditions import parse_if_match
from careerops.db.session import get_session
from careerops.domain.jobs import JobCreate, JobRecord, JobStatus, JobUpdate
from careerops.domain.users import UserAccount
from careerops.repositories.jobs import JobRepository
from careerops.schemas.jobs import JobCreateRequest, JobListResponse, JobResponse, JobUpdateRequest
from careerops.services.jobs import JobService, decode_job_cursor

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=HTTPStatus.CREATED)
async def create_job(
    payload: JobCreateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    service = build_job_service(session)
    job = await service.create_job(
        JobCreate(
            user_id=current_user.id,
            company=payload.company,
            title=payload.title,
            raw_description=payload.raw_description,
            source_url=payload.source_url,
            location=payload.location,
            deadline=payload.deadline,
            status=payload.status,
        )
    )
    return to_response(job)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Annotated[JobStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JobListResponse:
    service = build_job_service(session)
    jobs, next_cursor = await service.list_jobs(
        user_id=current_user.id,
        status=status,
        cursor=decode_job_cursor(cursor),
        limit=limit,
    )
    return JobListResponse(items=[to_response(job) for job in jobs], next_cursor=next_cursor)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobResponse:
    service = build_job_service(session)
    job = await service.get_job(current_user.id, job_id)
    return to_response(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    payload: JobUpdateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JobResponse:
    expected_version = parse_if_match(if_match)
    service = build_job_service(session)
    job = await service.update_job(
        user_id=current_user.id,
        job_id=job_id,
        expected_version=expected_version,
        payload=JobUpdate(
            company=payload.company,
            title=payload.title,
            raw_description=payload.raw_description,
            source_url=payload.source_url,
            clear_source_url=(
                payload.source_url is None and "source_url" in payload.model_fields_set
            ),
            location=payload.location,
            clear_location=payload.location is None and "location" in payload.model_fields_set,
            deadline=payload.deadline,
            clear_deadline=payload.deadline is None and "deadline" in payload.model_fields_set,
            status=payload.status,
        ),
    )
    return to_response(job)


@router.delete("/{job_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_job(
    job_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    service = build_job_service(session)
    await service.delete_job(current_user.id, job_id)


def build_job_service(session: AsyncSession) -> JobService:
    return JobService(JobRepository(session))


def to_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        company=job.company,
        title=job.title,
        raw_description=job.raw_description,
        description_hash=job.description_hash,
        source_url=job.source_url,
        location=job.location,
        deadline=job.deadline,
        status=job.status,
        version=job.version,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
