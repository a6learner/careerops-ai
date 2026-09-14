from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.api.preconditions import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    parse_idempotency_key,
    parse_if_match,
)
from careerops.db.session import get_session
from careerops.domain.action_items import (
    ActionItemCreate,
    ActionItemRecord,
    ActionItemStatus,
    ActionItemUpdate,
)
from careerops.domain.users import UserAccount
from careerops.repositories.action_items import ActionItemRepository
from careerops.repositories.jobs import JobRepository
from careerops.schemas.action_items import (
    ActionItemCreateRequest,
    ActionItemListResponse,
    ActionItemResponse,
    ActionItemUpdateRequest,
)
from careerops.services.action_items import ActionItemService, decode_action_item_cursor

router = APIRouter(prefix="/api/v1/action-items", tags=["action-items"])


@router.post("", response_model=ActionItemResponse, status_code=HTTPStatus.CREATED)
async def create_action_item(
    payload: ActionItemCreateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=MAX_IDEMPOTENCY_KEY_LENGTH),
    ] = None,
) -> ActionItemResponse:
    item = await build_action_item_service(session).create_action_item(
        ActionItemCreate(
            user_id=current_user.id,
            job_id=payload.job_id,
            title=payload.title,
            source_evidence_match_id=payload.source_evidence_match_id,
            idempotency_key=parse_idempotency_key(idempotency_key),
        )
    )
    return to_response(item)


@router.get("", response_model=ActionItemListResponse)
async def list_action_items(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Annotated[ActionItemStatus | None, Query()] = None,
    job_id: Annotated[UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ActionItemListResponse:
    items, next_cursor = await build_action_item_service(session).list_action_items(
        user_id=current_user.id,
        status=status,
        job_id=job_id,
        cursor=decode_action_item_cursor(cursor),
        limit=limit,
    )
    return ActionItemListResponse(
        items=[to_response(item) for item in items],
        next_cursor=next_cursor,
    )


@router.patch("/{action_item_id}", response_model=ActionItemResponse)
async def update_action_item(
    action_item_id: UUID,
    payload: ActionItemUpdateRequest,
    current_user: Annotated[UserAccount, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ActionItemResponse:
    item = await build_action_item_service(session).update_action_item(
        user_id=current_user.id,
        action_item_id=action_item_id,
        expected_version=parse_if_match(if_match),
        payload=ActionItemUpdate(title=payload.title, status=payload.status),
    )
    return to_response(item)


def build_action_item_service(session: AsyncSession) -> ActionItemService:
    return ActionItemService(
        jobs=JobRepository(session),
        action_items=ActionItemRepository(session),
    )


def to_response(item: ActionItemRecord) -> ActionItemResponse:
    return ActionItemResponse(
        id=item.id,
        job_id=item.job_id,
        source_evidence_match_id=item.source_evidence_match_id,
        title=item.title,
        status=item.status,
        version=item.version,
        job_is_archived=item.job_is_archived,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
