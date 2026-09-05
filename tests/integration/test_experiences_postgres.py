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
async def test_experience_crud_enforces_object_level_authorization() -> None:
    app = create_app()
    first_email = f"first-{uuid4()}@example.com"
    second_email = f"second-{uuid4()}@example.com"

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            first_token = await register_and_login(client, first_email)
            second_token = await register_and_login(client, second_email)

            created = await client.post(
                "/api/v1/experiences",
                headers=auth_header(first_token),
                json={
                    "title": "CareerOps AI",
                    "kind": "project",
                    "description": "Built FastAPI auth and PostgreSQL migrations.",
                    "skills": ["Python", "FastAPI", "PostgreSQL"],
                    "outcome": "Passed strict checks.",
                },
            )
            experience_id = created.json()["id"]

            first_list = await client.get("/api/v1/experiences", headers=auth_header(first_token))
            second_list = await client.get("/api/v1/experiences", headers=auth_header(second_token))
            unauthorized_get = await client.get(
                f"/api/v1/experiences/{experience_id}",
                headers=auth_header(second_token),
            )
            missing_if_match = await client.patch(
                f"/api/v1/experiences/{experience_id}",
                headers=auth_header(first_token),
                json={"title": "CareerOps AI Backend"},
            )
            stale_update = await client.patch(
                f"/api/v1/experiences/{experience_id}",
                headers={**auth_header(first_token), "If-Match": "99"},
                json={"title": "CareerOps AI Backend"},
            )
            updated = await client.patch(
                f"/api/v1/experiences/{experience_id}",
                headers={**auth_header(first_token), "If-Match": str(created.json()["version"])},
                json={"title": "CareerOps AI Backend", "outcome": None},
            )
            unauthorized_delete = await client.delete(
                f"/api/v1/experiences/{experience_id}",
                headers=auth_header(second_token),
            )
            deleted = await client.delete(
                f"/api/v1/experiences/{experience_id}",
                headers=auth_header(first_token),
            )
            get_after_delete = await client.get(
                f"/api/v1/experiences/{experience_id}",
                headers=auth_header(first_token),
            )

    assert created.status_code == 201
    assert created.json()["version"] == 1
    assert len(created.json()["content_hash"]) == 64

    assert first_list.status_code == 200
    assert len(first_list.json()["items"]) == 1
    assert second_list.status_code == 200
    assert second_list.json()["items"] == []

    assert unauthorized_get.status_code == 404
    assert unauthorized_get.json()["error"]["code"] == "EXPERIENCE_NOT_FOUND"

    assert missing_if_match.status_code == 428
    assert missing_if_match.json()["error"]["code"] == "IF_MATCH_REQUIRED"

    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "EXPERIENCE_VERSION_CONFLICT"

    assert updated.status_code == 200
    assert updated.json()["title"] == "CareerOps AI Backend"
    assert updated.json()["outcome"] is None
    assert updated.json()["version"] == 2
    assert updated.json()["content_hash"] != created.json()["content_hash"]

    assert unauthorized_delete.status_code == 404
    assert deleted.status_code == 204
    assert get_after_delete.status_code == 404


async def register_and_login(client: AsyncClient, email: str) -> str:
    password = "strong-password"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert registered.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert isinstance(token, str)
    return token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
