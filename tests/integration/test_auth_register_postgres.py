import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_register_user_persists_to_postgres_and_rejects_duplicate_email() -> None:
    app = create_app()
    email = f"student-{uuid4()}@example.com"

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            created = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "strong-password"},
            )
            duplicate = await client.post(
                "/api/v1/auth/register",
                json={"email": email.upper(), "password": "strong-password"},
            )
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email.upper(), "password": "strong-password"},
            )
            failed_login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
            )

    assert created.status_code == 201
    assert created.json()["email"] == email
    assert "password_hash" not in created.json()

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]

    assert failed_login.status_code == 401
    assert failed_login.json()["error"]["code"] == "INVALID_CREDENTIALS"
