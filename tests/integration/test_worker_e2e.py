import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1"
    or os.getenv("CAREEROPS_RUN_WORKER_E2E") != "1",
    reason="requires local PostgreSQL, Redis, and a running Dramatiq worker",
)
@pytest.mark.asyncio
async def test_api_dispatches_work_that_worker_completes() -> None:
    app = create_app()
    email = f"worker-e2e-{uuid4()}@example.com"
    password = "strong-password"

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password},
            )
            assert registered.status_code == 201
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            job = await client.post(
                "/api/v1/jobs",
                headers=headers,
                json={
                    "company": "Example",
                    "title": "Backend Intern",
                    "raw_description": "Python experience required. Preferred Redis.",
                },
            )
            run = await client.post(
                f"/api/v1/jobs/{job.json()['id']}/parse-runs",
                headers={**headers, "Idempotency-Key": f"worker-e2e-{uuid4()}"},
            )
            assert run.status_code == 202
            assert run.json()["status"] == "queued"

            path = f"/api/v1/jobs/{job.json()['id']}/parse-runs/{run.json()['id']}"
            completed = run
            for _ in range(450):
                completed = await client.get(path, headers=headers)
                if completed.json()["status"] in {"succeeded", "failed"}:
                    break
                await asyncio.sleep(0.1)

    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"
    assert len(completed.json()["requirements"]) == 2
