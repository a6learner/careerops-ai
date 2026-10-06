import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.adapters.evidence_matcher_factory import LIVE_MATCHER_ENV
from careerops.core.config import Settings
from careerops.db.models import Experience
from careerops.db.session import create_session_factory
from careerops.domain.analysis_runs import FAKE_ANALYSIS_MODEL_NAME
from careerops.domain.embeddings import FAKE_EMBEDDING_MODEL_NAME
from careerops.domain.parse_runs import FAKE_PARSE_MODEL_NAME
from careerops.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1"
    or os.getenv("CAREEROPS_RUN_WORKER_E2E") != "1",
    reason="requires local PostgreSQL, Redis, and a running Dramatiq worker",
)
@pytest.mark.asyncio
async def test_api_dispatches_work_that_worker_completes() -> None:
    settings = Settings()
    assert settings.llm_provider == "fake", "worker E2E must not call a real LLM provider"
    assert settings.evidence_matcher_provider == "fake", (
        "worker E2E must use the fake evidence matcher"
    )
    assert os.getenv(LIVE_MATCHER_ENV) != "1", (
        "worker E2E must not authorize the real evidence matcher"
    )
    assert settings.embedding_provider == "fake", (
        "worker E2E must not call a real embedding provider"
    )
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
            experience = await client.post(
                "/api/v1/experiences",
                headers=headers,
                json={
                    "title": "CareerOps AI",
                    "kind": "project",
                    "description": "Built reliable Python APIs with PostgreSQL.",
                    "skills": ["Python", "PostgreSQL"],
                    "outcome": "Added deterministic integration tests.",
                },
            )
            assert experience.status_code == 201
            session_factory = create_session_factory(settings.database_url)
            for _ in range(450):
                async with session_factory() as session:
                    stored_experience = await session.get(
                        Experience,
                        UUID(experience.json()["id"]),
                    )
                    if stored_experience is not None and stored_experience.embedding is not None:
                        break
                await asyncio.sleep(0.1)
            assert stored_experience is not None
            assert stored_experience.embedding is not None
            assert stored_experience.embedding_model == FAKE_EMBEDDING_MODEL_NAME

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
            completed_parse = run
            for _ in range(450):
                completed_parse = await client.get(path, headers=headers)
                if completed_parse.json()["status"] in {"succeeded", "failed"}:
                    break
                await asyncio.sleep(0.1)

            assert completed_parse.status_code == 200
            assert completed_parse.json()["status"] == "succeeded"
            assert completed_parse.json()["model_name"] == FAKE_PARSE_MODEL_NAME
            assert len(completed_parse.json()["requirements"]) == 2

            analysis = await client.post(
                f"/api/v1/jobs/{job.json()['id']}/analysis-runs",
                headers={**headers, "Idempotency-Key": f"worker-analysis-{uuid4()}"},
                json={"parse_run_id": completed_parse.json()["id"]},
            )
            assert analysis.status_code == 202
            analysis_path = (
                f"/api/v1/jobs/{job.json()['id']}/analysis-runs/{analysis.json()['id']}"
            )
            completed_analysis = analysis
            for _ in range(450):
                completed_analysis = await client.get(analysis_path, headers=headers)
                if completed_analysis.json()["status"] in {"succeeded", "failed"}:
                    break
                await asyncio.sleep(0.1)

            await session_factory.kw["bind"].dispose()

    assert completed_analysis.status_code == 200
    assert completed_analysis.json()["status"] == "succeeded"
    assert len(completed_analysis.json()["matches"]) == 2
    assert completed_analysis.json()["validation_failure_count"] == 0
    assert completed_analysis.json()["model_name"] == FAKE_ANALYSIS_MODEL_NAME
