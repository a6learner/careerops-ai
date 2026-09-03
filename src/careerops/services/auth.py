from typing import Protocol
from uuid import UUID

from careerops.domain.errors import InvalidCredentialsError, InvalidTokenError
from careerops.domain.users import UserAccount, UserCredentials
from careerops.security.passwords import PasswordHasher
from careerops.security.tokens import AccessToken, TokenIssuer, TokenVerifier


class UserCreator(Protocol):
    async def create_user(self, email: str, password_hash: str) -> UserAccount: ...

    async def commit(self) -> None: ...


class UserAuthenticator(UserCreator, Protocol):
    async def get_credentials_by_email(self, email: str) -> UserCredentials | None: ...

    async def get_account_by_id(self, user_id: UUID) -> UserAccount | None: ...


class AuthService:
    def __init__(
        self,
        users: UserAuthenticator,
        password_hasher: PasswordHasher,
        token_issuer: TokenIssuer,
        token_verifier: TokenVerifier,
    ) -> None:
        self._users = users
        self._password_hasher = password_hasher
        self._token_issuer = token_issuer
        self._token_verifier = token_verifier

    async def register_user(self, email: str, plain_password: str) -> UserAccount:
        password_hash = self._password_hasher.hash(plain_password)
        user = await self._users.create_user(email=email, password_hash=password_hash)
        await self._users.commit()
        return user

    async def login_user(self, email: str, plain_password: str) -> AccessToken:
        credentials = await self._users.get_credentials_by_email(email)
        if credentials is None:
            raise InvalidCredentialsError()
        if not self._password_hasher.verify(plain_password, credentials.password_hash):
            raise InvalidCredentialsError()
        return self._token_issuer.issue_access_token(credentials.id)

    async def get_current_user_from_token(self, token: str) -> UserAccount:
        user_id = self._token_verifier.verify_access_token(token)
        user = await self._users.get_account_by_id(user_id)
        if user is None:
            raise InvalidTokenError()
        return user
