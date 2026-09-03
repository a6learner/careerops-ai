from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import InvalidCredentialsError
from careerops.domain.users import UserAccount, UserCredentials
from careerops.security.passwords import PasswordHasher
from careerops.security.tokens import TokenIssuer, TokenVerifier
from careerops.services.auth import AuthService


class InMemoryUsers:
    def __init__(self) -> None:
        self.created_password_hash: str | None = None
        self.committed = False
        self.credentials: UserCredentials | None = None

    async def create_user(self, email: str, password_hash: str) -> UserAccount:
        self.created_password_hash = password_hash
        return UserAccount(id=uuid4(), email=email, created_at=datetime.now(UTC))

    async def get_credentials_by_email(self, email: str) -> UserCredentials | None:
        if self.credentials is None or self.credentials.email != email:
            return None
        return self.credentials

    async def get_account_by_id(self, user_id: UUID) -> UserAccount | None:
        return None

    async def commit(self) -> None:
        self.committed = True


def build_service(users: InMemoryUsers) -> AuthService:
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
async def test_login_user_issues_access_token_for_valid_password() -> None:
    password_hash = PasswordHasher.recommended().hash("correct-password")
    users = InMemoryUsers()
    users.credentials = UserCredentials(
        id=uuid4(),
        email="student@example.com",
        password_hash=password_hash,
    )

    token = await build_service(users).login_user("student@example.com", "correct-password")

    assert token.token_type == "bearer"
    assert token.value


@pytest.mark.asyncio
async def test_login_user_rejects_unknown_email() -> None:
    users = InMemoryUsers()

    with pytest.raises(InvalidCredentialsError):
        await build_service(users).login_user("missing@example.com", "correct-password")


@pytest.mark.asyncio
async def test_login_user_rejects_wrong_password() -> None:
    password_hash = PasswordHasher.recommended().hash("correct-password")
    users = InMemoryUsers()
    users.credentials = UserCredentials(
        id=uuid4(),
        email="student@example.com",
        password_hash=password_hash,
    )

    with pytest.raises(InvalidCredentialsError):
        await build_service(users).login_user("student@example.com", "wrong-password")
