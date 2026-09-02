from datetime import UTC, datetime
from uuid import uuid4

import pytest

from careerops.domain.users import UserAccount
from careerops.security.passwords import PasswordHasher
from careerops.services.auth import AuthService


class InMemoryUserCreator:
    def __init__(self) -> None:
        self.created_password_hash: str | None = None
        self.committed = False

    async def create_user(self, email: str, password_hash: str) -> UserAccount:
        self.created_password_hash = password_hash
        return UserAccount(id=uuid4(), email=email, created_at=datetime.now(UTC))

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_register_user_hashes_password_before_persisting() -> None:
    users = InMemoryUserCreator()
    service = AuthService(users, PasswordHasher.recommended())

    user = await service.register_user("student@example.com", "correct horse battery staple")

    assert user.email == "student@example.com"
    assert users.created_password_hash is not None
    assert users.created_password_hash != "correct horse battery staple"
    assert PasswordHasher.recommended().verify(
        "correct horse battery staple",
        users.created_password_hash,
    )


@pytest.mark.asyncio
async def test_register_user_commits_created_user() -> None:
    users = InMemoryUserCreator()
    service = AuthService(users, PasswordHasher.recommended())

    await service.register_user("student@example.com", "correct horse battery staple")

    assert users.committed
