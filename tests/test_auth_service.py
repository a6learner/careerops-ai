from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from careerops.domain.users import UserAccount, UserCredentials
from careerops.security.passwords import PasswordHasher
from careerops.security.tokens import TokenIssuer, TokenVerifier
from careerops.services.auth import AuthService


class InMemoryUserCreator:
    def __init__(self) -> None:
        self.created_password_hash: str | None = None
        self.committed = False

    async def create_user(self, email: str, password_hash: str) -> UserAccount:
        self.created_password_hash = password_hash
        return UserAccount(id=uuid4(), email=email, created_at=datetime.now(UTC))

    async def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        return None

    async def get_account_by_id(self, user_id: UUID) -> UserAccount | None:
        return None

    async def commit(self) -> None:
        self.committed = True


def build_service(users: InMemoryUserCreator) -> AuthService:
    return AuthService(
        users,
        PasswordHasher.recommended(),
        TokenIssuer(
            secret="test-secret-with-at-least-32-bytes",
            expires_after=timedelta(minutes=30),
        ),
        TokenVerifier(secret="test-secret-with-at-least-32-bytes"),
    )


@pytest.mark.asyncio
async def test_register_user_hashes_password_before_persisting() -> None:
    users = InMemoryUserCreator()
    service = build_service(users)

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
    service = build_service(users)

    await service.register_user("student@example.com", "correct horse battery staple")

    assert users.committed
