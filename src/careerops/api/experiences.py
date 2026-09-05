from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.api.preconditions import parse_if_match
from careerops.db.session import get_session
from careerops.domain.experiences import ExperienceCreate, ExperienceRecord, ExperienceUpdate
from careerops.domain.users import UserAccount
from careerops.repositories.experiences import ExperienceRepository
from careerops.schemas.experiences import (
    ExperienceCreateRequest,
    ExperienceListResponse,
    ExperienceResponse,
    ExperienceUpdateRequest,
)
from careerops.services.experiences import ExperienceService

router = APIRouter(prefix="/api/v1/experiences", tags=["experiences"])


@router.post("", response_model=ExperienceResponse, status_code=HTTPStatus.CREATED)
async def create_experience(
    payload: ExperienceCreateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperienceResponse:
    service = build_experience_service(session)
    experience = await service.create_experience(
        ExperienceCreate(
            user_id=current_user.id,
            title=payload.title,
            kind=payload.kind,
            description=payload.description,
            skills=tuple(payload.skills),
            outcome=payload.outcome,
        )
    )
    return to_response(experience)


@router.get("", response_model=ExperienceListResponse)
async def list_experiences(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperienceListResponse:
    service = build_experience_service(session)
    experiences = await service.list_experiences(current_user.id)
    return ExperienceListResponse(items=[to_response(experience) for experience in experiences])


@router.get("/{experience_id}", response_model=ExperienceResponse)
async def get_experience(
    experience_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExperienceResponse:
    service = build_experience_service(session)
    experience = await service.get_experience(current_user.id, experience_id)
    return to_response(experience)


@router.patch("/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: UUID,
    payload: ExperienceUpdateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ExperienceResponse:
    expected_version = parse_if_match(if_match)
    service = build_experience_service(session)
    experience = await service.update_experience(
        user_id=current_user.id,
        experience_id=experience_id,
        expected_version=expected_version,
        payload=ExperienceUpdate(
            title=payload.title,
            kind=payload.kind,
            description=payload.description,
            skills=tuple(payload.skills) if payload.skills is not None else None,
            outcome=payload.outcome,
            clear_outcome=payload.outcome is None and "outcome" in payload.model_fields_set,
        ),
    )
    return to_response(experience)


@router.delete("/{experience_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_experience(
    experience_id: UUID,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    service = build_experience_service(session)
    await service.delete_experience(current_user.id, experience_id)


def build_experience_service(session: AsyncSession) -> ExperienceService:
    return ExperienceService(ExperienceRepository(session))


def to_response(experience: ExperienceRecord) -> ExperienceResponse:
    return ExperienceResponse(
        id=experience.id,
        title=experience.title,
        kind=experience.kind,
        description=experience.description,
        skills=list(experience.skills),
        outcome=experience.outcome,
        version=experience.version,
        content_hash=experience.content_hash,
        created_at=experience.created_at,
        updated_at=experience.updated_at,
    )
