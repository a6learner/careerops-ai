from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.core.config import get_settings
from careerops.db.session import get_session
from careerops.domain.errors import InvalidTokenError, MissingTokenError
from careerops.domain.users import UserAccount
from careerops.repositories.users import UserRepository
from careerops.security.passwords import PasswordHasher
from careerops.security.tokens import TokenIssuer, TokenVerifier
from careerops.services.auth import AuthService


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> UserAccount:
    if authorization is None:
        raise MissingTokenError()

    scheme, separator, token = authorization.partition(" ")
    if separator == "" or scheme.lower() != "bearer" or token.strip() == "":
        raise InvalidTokenError()

    settings = get_settings()
    service = AuthService(
        users=UserRepository(session),
        password_hasher=PasswordHasher.recommended(),
        token_issuer=TokenIssuer(
            secret=settings.jwt_secret,
            expires_after=timedelta(minutes=settings.access_token_expire_minutes),
        ),
        token_verifier=TokenVerifier(secret=settings.jwt_secret),
    )
    return await service.get_current_user_from_token(token.strip())
