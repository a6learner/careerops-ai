from datetime import timedelta
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dependencies import get_current_user
from careerops.core.config import Settings, get_settings
from careerops.db.session import get_session
from careerops.domain.users import UserAccount
from careerops.repositories.users import UserRepository
from careerops.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisteredUserResponse,
    RegisterUserRequest,
)
from careerops.security.passwords import PasswordHasher
from careerops.security.tokens import TokenIssuer, TokenVerifier
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
    settings = get_settings()
    service = build_auth_service(session, settings)
    user = await service.register_user(email=payload.email, plain_password=payload.password)
    return RegisteredUserResponse(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/login", response_model=AccessTokenResponse)
async def login_user(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccessTokenResponse:
    settings = get_settings()
    service = build_auth_service(session, settings)
    token = await service.login_user(email=payload.email, plain_password=payload.password)
    return AccessTokenResponse(access_token=token.value, token_type=token.token_type)


@router.get("/me", response_model=RegisteredUserResponse)
async def get_me(
    current_user: Annotated[UserAccount, Depends(get_current_user)],
) -> RegisteredUserResponse:
    return RegisteredUserResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )


def build_auth_service(session: AsyncSession, settings: Settings) -> AuthService:
    token_issuer = TokenIssuer(
        secret=settings.jwt_secret,
        expires_after=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return AuthService(
        UserRepository(session),
        PasswordHasher.recommended(),
        token_issuer,
        TokenVerifier(secret=settings.jwt_secret),
    )
