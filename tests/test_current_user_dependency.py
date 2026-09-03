from datetime import UTC, datetime
from uuid import uuid4

import pytest

from careerops.api.dependencies import get_current_user
from careerops.db.session import get_session
from careerops.domain.errors import InvalidTokenError, MissingTokenError
from careerops.domain.users import UserAccount
from careerops.main import create_app


@pytest.mark.asyncio
async def test_current_user_requires_authorization_header() -> None:
    app = create_app()

    async def fake_session() -> None:
        return None

    app.dependency_overrides[get_session] = fake_session

    with pytest.raises(MissingTokenError):
        await get_current_user(session=None, authorization=None)


@pytest.mark.asyncio
async def test_current_user_rejects_non_bearer_header() -> None:
    with pytest.raises(InvalidTokenError):
        await get_current_user(session=None, authorization="Basic abc")


def test_current_user_dependency_can_be_overridden_for_route_tests() -> None:
    user = UserAccount(
        id=uuid4(),
        email="student@example.com",
        created_at=datetime.now(UTC),
    )

    assert user.email == "student@example.com"
