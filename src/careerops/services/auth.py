from typing import Protocol

from careerops.domain.users import UserAccount
from careerops.security.passwords import PasswordHasher


class UserCreator(Protocol):
    async def create_user(self, email: str, password_hash: str) -> UserAccount: ...

    async def commit(self) -> None: ...


class AuthService:
    def __init__(self, users: UserCreator, password_hasher: PasswordHasher) -> None:
        self._users = users
        self._password_hasher = password_hasher

    async def register_user(self, email: str, plain_password: str) -> UserAccount:
        password_hash = self._password_hasher.hash(plain_password)
        user = await self._users.create_user(email=email, password_hash=password_hash)
        await self._users.commit()
        return user
