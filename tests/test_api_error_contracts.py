import pytest
from httpx import ASGITransport, AsyncClient

from careerops.api.dependencies import get_current_user
from careerops.db.session import get_session
from careerops.domain.users import UserAccount
from careerops.main import create_app


@pytest.mark.asyncio
async def test_request_validation_errors_use_project_error_contract() -> None:
    app = create_app()

    async def fake_session() -> None:
        return None

    app.dependency_overrides[get_session] = fake_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "strong-password"},
            headers={"x-request-id": "test-request-id"},
        )

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed."
    assert body["error"]["request_id"] == "test-request-id"
    assert body["error"]["details"]["errors"][0]["location"] == "body.email"


@pytest.mark.asyncio
async def test_malformed_if_match_uses_project_error_contract() -> None:
    app = create_app()

    async def fake_current_user() -> UserAccount:
        from datetime import UTC, datetime
        from uuid import uuid4

        return UserAccount(
            id=uuid4(),
            email="student@example.com",
            created_at=datetime.now(UTC),
        )

    async def fake_session() -> None:
        return None

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_session] = fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000",
            json={"status": "applied"},
            headers={"If-Match": "abc", "x-request-id": "bad-if-match"},
        )

    body = response.json()
    assert response.status_code == 428
    assert body["error"]["code"] == "IF_MATCH_REQUIRED"
    assert body["error"]["details"] == {}
    assert body["error"]["request_id"] == "bad-if-match"
