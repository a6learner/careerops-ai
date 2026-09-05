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
async def test_jobs_crud_paginates_and_enforces_object_level_authorization() -> None:
    app = create_app()
    first_email = f"jobs-first-{uuid4()}@example.com"
    second_email = f"jobs-second-{uuid4()}@example.com"

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            first_token = await register_and_login(client, first_email)
            second_token = await register_and_login(client, second_email)

            created = await client.post(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                json={
                    "company": "OpenAI",
                    "title": "Backend Engineer Intern",
                    "raw_description": "Build reliable APIs with Python and PostgreSQL.",
                    "status": "saved",
                },
            )
            second_created = await client.post(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                json={
                    "company": "Anthropic",
                    "title": "Platform Engineer Intern",
                    "raw_description": "Work on distributed systems and reliability.",
                    "status": "preparing",
                },
            )
            job_id = created.json()["id"]

            first_page = await client.get(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                params={"limit": 1},
            )
            second_page = await client.get(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                params={"limit": 1, "cursor": first_page.json()["next_cursor"]},
            )
            filtered = await client.get(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                params={"status": "preparing"},
            )
            other_user_list = await client.get("/api/v1/jobs", headers=auth_header(second_token))
            unauthorized_get = await client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_header(second_token),
            )
            missing_if_match = await client.patch(
                f"/api/v1/jobs/{job_id}",
                headers=auth_header(first_token),
                json={"status": "applied"},
            )
            stale_update = await client.patch(
                f"/api/v1/jobs/{job_id}",
                headers={**auth_header(first_token), "If-Match": "99"},
                json={"status": "applied"},
            )
            updated = await client.patch(
                f"/api/v1/jobs/{job_id}",
                headers={**auth_header(first_token), "If-Match": str(created.json()["version"])},
                json={
                    "status": "applied",
                    "source_url": None,
                    "location": None,
                    "deadline": None,
                },
            )
            unauthorized_delete = await client.delete(
                f"/api/v1/jobs/{job_id}",
                headers=auth_header(second_token),
            )
            deleted = await client.delete(
                f"/api/v1/jobs/{job_id}",
                headers=auth_header(first_token),
            )
            get_after_delete = await client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_header(first_token),
            )

    assert created.status_code == 201
    assert created.json()["version"] == 1
    assert len(created.json()["description_hash"]) == 64
    assert created.json()["source_url"] is None
    assert created.json()["location"] is None
    assert created.json()["deadline"] is None
    assert second_created.status_code == 201

    assert first_page.status_code == 200
    assert len(first_page.json()["items"]) == 1
    assert first_page.json()["next_cursor"]
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1
    assert second_page.json()["next_cursor"] is None

    assert filtered.status_code == 200
    assert [item["company"] for item in filtered.json()["items"]] == ["Anthropic"]
    assert other_user_list.status_code == 200
    assert other_user_list.json()["items"] == []

    assert unauthorized_get.status_code == 404
    assert unauthorized_get.json()["error"]["code"] == "JOB_NOT_FOUND"

    assert missing_if_match.status_code == 428
    assert missing_if_match.json()["error"]["code"] == "IF_MATCH_REQUIRED"

    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "JOB_VERSION_CONFLICT"

    assert updated.status_code == 200
    assert updated.json()["status"] == "applied"
    assert updated.json()["version"] == 2
    assert updated.json()["description_hash"] == created.json()["description_hash"]

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
