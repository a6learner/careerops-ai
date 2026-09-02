from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.db.session import get_session
from careerops.repositories.users import UserRepository
from careerops.schemas.auth import RegisteredUserResponse, RegisterUserRequest
from careerops.security.passwords import PasswordHasher
from careerops.services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisteredUserResponse,
    status_code=HTTPStatus.CREATED,
)
async def register_user(
    payload: RegisterUserRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegisteredUserResponse:
    service = AuthService(UserRepository(session), PasswordHasher.recommended())
    user = await service.register_user(email=payload.email, plain_password=payload.password)
    return RegisteredUserResponse(id=user.id, email=user.email, created_at=user.created_at)
