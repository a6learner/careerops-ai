from typing import Protocol

from careerops.domain.errors import InvalidCredentialsError
from careerops.domain.users import UserAccount, UserCredentials
from careerops.security.passwords import PasswordHasher
from careerops.security.tokens import AccessToken, TokenIssuer


class UserCreator(Protocol):
    async def create_user(self, email: str, password_hash: str) -> UserAccount: ...

    async def commit(self) -> None: ...


class UserAuthenticator(UserCreator, Protocol):
    async def get_credentials_by_email(self, email: str) -> UserCredentials | None: ...


class AuthService:
    def __init__(
        self,
        users: UserAuthenticator,
        password_hasher: PasswordHasher,
        token_issuer: TokenIssuer,
    ) -> None:
        self._users = users
        self._password_hasher = password_hasher
        self._token_issuer = token_issuer

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
