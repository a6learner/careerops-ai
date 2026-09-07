import asyncio
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
async def test_parse_runs_are_idempotent_and_authorized() -> None:
    app = create_app()
    first_email = f"parse-first-{uuid4()}@example.com"
    second_email = f"parse-second-{uuid4()}@example.com"

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            first_token = await register_and_login(client, first_email)
            second_token = await register_and_login(client, second_email)
            created_job = await client.post(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                json={
                    "company": "OpenAI",
                    "title": "Backend Engineer Intern",
                    "raw_description": (
                        "Python experience required. Preferred Redis. "
                        "Build reliable APIs."
                    ),
                },
            )
            job_id = created_job.json()["id"]

            missing_key = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers=auth_header(first_token),
            )
            submitted = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "parse-key"},
            )
            repeated = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "parse-key"},
            )
            concurrent_first, concurrent_second = await asyncio.gather(
                client.post(
                    f"/api/v1/jobs/{job_id}/parse-runs",
                    headers={
                        **auth_header(first_token),
                        "Idempotency-Key": "concurrent-key",
                    },
                ),
                client.post(
                    f"/api/v1/jobs/{job_id}/parse-runs",
                    headers={
                        **auth_header(first_token),
                        "Idempotency-Key": "concurrent-key",
                    },
                ),
            )
            second_job = await client.post(
                "/api/v1/jobs",
                headers=auth_header(first_token),
                json={
                    "company": "Example",
                    "title": "Platform Intern",
                    "raw_description": "SQL experience required.",
                },
            )
            scoped_to_second_job = await client.post(
                f"/api/v1/jobs/{second_job.json()['id']}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "parse-key"},
            )
            updated_job = await client.patch(
                f"/api/v1/jobs/{job_id}",
                headers={**auth_header(first_token), "If-Match": "1"},
                json={"raw_description": "Go experience required."},
            )
            conflicting_replay = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "parse-key"},
            )
            oversized_key = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "x" * 256},
            )
            fetched = await client.get(
                f"/api/v1/jobs/{job_id}/parse-runs/{submitted.json()['id']}",
                headers=auth_header(first_token),
            )
            unauthorized = await client.get(
                f"/api/v1/jobs/{job_id}/parse-runs/{submitted.json()['id']}",
                headers=auth_header(second_token),
            )

    assert created_job.status_code == 201

    assert missing_key.status_code == 428
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    assert submitted.status_code == 202
    assert submitted.json()["status"] == "succeeded"
    assert submitted.json()["model_name"] == "local-fake-parser"
    assert submitted.json()["prompt_version"] == "parse-v1"
    assert len(submitted.json()["requirements"]) == 3
    assert submitted.json()["requirements"][0]["category"] == "must_have"
    assert submitted.json()["requirements"][0]["skill_normalized"] == "python"
    assert submitted.json()["requirements"][0]["source_span_start"] == 0

    assert repeated.status_code == 202
    assert repeated.json()["id"] == submitted.json()["id"]
    assert repeated.json()["requirements"] == submitted.json()["requirements"]

    assert concurrent_first.status_code == 202
    assert concurrent_second.status_code == 202
    assert concurrent_first.json()["id"] == concurrent_second.json()["id"]
    assert concurrent_first.json()["requirements"] == concurrent_second.json()["requirements"]

    assert second_job.status_code == 201
    assert scoped_to_second_job.status_code == 202
    assert scoped_to_second_job.json()["job_id"] == second_job.json()["id"]
    assert scoped_to_second_job.json()["id"] != submitted.json()["id"]

    assert updated_job.status_code == 200
    assert conflicting_replay.status_code == 409
    assert conflicting_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    assert oversized_key.status_code == 422
    assert oversized_key.json()["error"]["code"] == "VALIDATION_ERROR"

    assert fetched.status_code == 200
    assert fetched.json()["id"] == submitted.json()["id"]
    assert fetched.json()["requirements"] == submitted.json()["requirements"]

    assert unauthorized.status_code == 404
    assert unauthorized.json()["error"]["code"] == "JOB_NOT_FOUND"


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
