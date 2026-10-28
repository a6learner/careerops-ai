from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.api.preconditions import parse_idempotency_key, parse_if_match
from careerops.db.session import get_session
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointPage,
    CheckpointRecord,
    ProjectInput,
    ProjectPage,
    ProjectRecord,
    RecordStatus,
    ReviewInput,
)
from careerops.domain.users import UserAccount
from careerops.repositories.project_records import ProjectRecordRepository
from careerops.services.project_records import ProjectRecordService

router = APIRouter(prefix="/api/v1/projects", tags=["project-records"])
CurrentUser = Annotated[UserAccount, Depends(get_current_user)]


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProjectRecordService:
    return ProjectRecordService(ProjectRecordRepository(session))


Service = Annotated[ProjectRecordService, Depends(get_service)]
Key = Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)]


@router.post("", response_model=ProjectRecord, status_code=201)
async def create_project(
    payload: ProjectInput,
    current_user: CurrentUser,
    service: Service,
    key: Key = None,
) -> ProjectRecord:
    return await service.create_project(current_user.id, parse_idempotency_key(key), payload)


@router.get("", response_model=ProjectPage)
async def list_projects(
    current_user: CurrentUser,
    service: Service,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProjectPage:
    return await service.list_projects(current_user.id, cursor, limit)


@router.get("/{project_id}", response_model=ProjectRecord)
async def get_project(
    project_id: UUID,
    current_user: CurrentUser,
    service: Service,
) -> ProjectRecord:
    return await service.get_project(current_user.id, project_id)


@router.post("/{project_id}/checkpoints", response_model=CheckpointRecord, status_code=201)
async def create_checkpoint(
    project_id: UUID,
    payload: CheckpointInput,
    current_user: CurrentUser,
    service: Service,
    key: Key = None,
) -> CheckpointRecord:
    return await service.create_checkpoint(
        current_user.id,
        project_id,
        parse_idempotency_key(key),
        payload,
    )


@router.get("/{project_id}/checkpoints", response_model=CheckpointPage)
async def list_checkpoints(
    project_id: UUID,
    current_user: CurrentUser,
    service: Service,
    status: Annotated[RecordStatus | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CheckpointPage:
    return await service.list_checkpoints(current_user.id, project_id, status, q, cursor, limit)


@router.get("/{project_id}/checkpoints/{checkpoint_id}", response_model=CheckpointRecord)
async def get_checkpoint(
    project_id: UUID,
    checkpoint_id: UUID,
    current_user: CurrentUser,
    service: Service,
) -> CheckpointRecord:
    return await service.get_checkpoint(current_user.id, project_id, checkpoint_id)


@router.patch("/{project_id}/checkpoints/{checkpoint_id}/review", response_model=CheckpointRecord)
async def review_checkpoint(
    project_id: UUID,
    checkpoint_id: UUID,
    payload: ReviewInput,
    current_user: CurrentUser,
    service: Service,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> CheckpointRecord:
    return await service.review_checkpoint(
        current_user.id,
        project_id,
        checkpoint_id,
        parse_if_match(if_match),
        payload,
    )
