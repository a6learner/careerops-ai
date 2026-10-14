import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.adapters.fake_job_search import FakeJobSearchProvider
from careerops.core.config import Settings
from careerops.db.session import create_session_factory
from careerops.domain.dashboard import DashboardSummary
from careerops.main import create_app
from careerops.repositories.assisted_imports import AssistedImportRepository
from careerops.services.assisted_imports import (
    CvImportExecutionService,
    JobDiscoveryExecutionService,
)

pytestmark = pytest.mark.integration


class NoopDispatcher:
    async def dispatch(self, run_id: UUID) -> None:
        del run_id


class NoopDashboardCache:
    async def get(self, user_id: UUID) -> DashboardSummary | None:
        del user_id
        return None

    async def set(self, user_id: UUID, summary: DashboardSummary) -> None:
        del user_id, summary

    async def invalidate(self, user_id: UUID) -> None:
        del user_id


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_assisted_imports_require_review_and_enforce_ownership() -> None:
    settings = Settings()
    assert settings.embedding_provider == "fake"
    app = create_app()
    first_email = f"assisted-first-{uuid4()}@example.com"
    second_email = f"assisted-second-{uuid4()}@example.com"
    session_factory = create_session_factory(settings.database_url)

    async with app.router.lifespan_context(app):
        app.state.cv_import_dispatcher = NoopDispatcher()
        app.state.job_discovery_dispatcher = NoopDispatcher()
        app.state.embedding_run_dispatcher = NoopDispatcher()
        app.state.dashboard_cache = NoopDashboardCache()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            first_token = await register_and_login(client, first_email)
            second_token = await register_and_login(client, second_email)
            first_headers = auth_header(first_token)
            second_headers = auth_header(second_token)

            submitted = await client.post(
                "/api/v1/cv-imports",
                headers={**first_headers, "Idempotency-Key": f"cv-{uuid4()}"},
                files={
                    "file": (
                        "resume.md",
                        b"CareerOps AI\nBuilt reliable APIs.",
                        "text/markdown",
                    )
                },
            )
            assert submitted.status_code == 202
            assert submitted.json()["status"] == "queued"
            assert (await client.get("/api/v1/experiences", headers=first_headers)).json()[
                "items"
            ] == []

            cv_import_id = UUID(submitted.json()["id"])
            async with session_factory() as session:
                executed = await CvImportExecutionService(
                    AssistedImportRepository(session)
                ).execute(cv_import_id)
            assert executed is True

            completed = await client.get(
                f"/api/v1/cv-imports/{cv_import_id}", headers=first_headers
            )
            assert completed.status_code == 200
            assert completed.json()["status"] == "succeeded"
            assert len(completed.json()["drafts"]) == 1
            assert (await client.get("/api/v1/experiences", headers=first_headers)).json()[
                "items"
            ] == []
            assert (
                await client.get(
                    f"/api/v1/cv-imports/{cv_import_id}", headers=second_headers
                )
            ).status_code == 404

            draft_id = completed.json()["drafts"][0]["id"]
            assert (
                await client.post(
                    f"/api/v1/experience-drafts/{draft_id}/confirm",
                    headers=second_headers,
                )
            ).status_code == 404
            confirmed = await client.post(
                f"/api/v1/experience-drafts/{draft_id}/confirm", headers=first_headers
            )
            replayed = await client.post(
                f"/api/v1/experience-drafts/{draft_id}/confirm", headers=first_headers
            )
            assert confirmed.status_code == 201
            assert replayed.status_code == 201
            assert replayed.json()["id"] == confirmed.json()["id"]
            experiences = await client.get("/api/v1/experiences", headers=first_headers)
            assert len(experiences.json()["items"]) == 1

            concurrent_import = await client.post(
                "/api/v1/cv-imports",
                headers={**first_headers, "Idempotency-Key": f"cv-{uuid4()}"},
                files={
                    "file": (
                        "second.md",
                        b"Concurrent confirmation\nCreates one Experience.",
                        "text/markdown",
                    )
                },
            )
            concurrent_import_id = UUID(concurrent_import.json()["id"])
            async with session_factory() as session:
                await CvImportExecutionService(AssistedImportRepository(session)).execute(
                    concurrent_import_id
                )
            concurrent_record = await client.get(
                f"/api/v1/cv-imports/{concurrent_import_id}", headers=first_headers
            )
            concurrent_draft_id = concurrent_record.json()["drafts"][0]["id"]
            concurrent_confirmations = await asyncio.gather(
                client.post(
                    f"/api/v1/experience-drafts/{concurrent_draft_id}/confirm",
                    headers=first_headers,
                ),
                client.post(
                    f"/api/v1/experience-drafts/{concurrent_draft_id}/confirm",
                    headers=first_headers,
                ),
            )
            assert {response.status_code for response in concurrent_confirmations} == {201}
            assert len({response.json()["id"] for response in concurrent_confirmations}) == 1
            experiences = await client.get("/api/v1/experiences", headers=first_headers)
            assert len(experiences.json()["items"]) == 2

            discovery = await client.post(
                "/api/v1/job-discovery-runs",
                headers={**first_headers, "Idempotency-Key": f"search-{uuid4()}"},
                json={
                    "query": "Backend Engineer",
                    "location": "Los Angeles",
                    "remote": None,
                    "published_within_days": 14,
                },
            )
            assert discovery.status_code == 202
            run_id = UUID(discovery.json()["id"])
            async with session_factory() as session:
                executed = await JobDiscoveryExecutionService(
                    AssistedImportRepository(session), FakeJobSearchProvider()
                ).execute(run_id)
            assert executed is True

            run = await client.get(
                f"/api/v1/job-discovery-runs/{run_id}", headers=first_headers
            )
            assert run.status_code == 200
            assert run.json()["status"] == "succeeded"
            assert len(run.json()["results"]) == 2
            assert all(result["observed_at"] for result in run.json()["results"])
            assert (
                await client.get(
                    f"/api/v1/job-discovery-runs/{run_id}", headers=second_headers
                )
            ).status_code == 404

            full_result = next(
                result for result in run.json()["results"] if result["raw_description"]
            )
            job_draft = await client.post(
                f"/api/v1/job-discovery-results/{full_result['id']}/draft",
                headers=first_headers,
            )
            assert job_draft.status_code == 201
            job_draft_id = job_draft.json()["id"]
            assert (
                await client.post(
                    f"/api/v1/job-drafts/{job_draft_id}/confirm",
                    headers=second_headers,
                )
            ).status_code == 404
            job = await client.post(
                f"/api/v1/job-drafts/{job_draft_id}/confirm", headers=first_headers
            )
            replayed_job = await client.post(
                f"/api/v1/job-drafts/{job_draft_id}/confirm", headers=first_headers
            )
            assert job.status_code == 201
            assert replayed_job.json()["id"] == job.json()["id"]
            jobs = await client.get("/api/v1/jobs", headers=first_headers)
            assert len(jobs.json()["items"]) == 1

            incomplete_result = next(
                result for result in run.json()["results"] if not result["raw_description"]
            )
            incomplete_draft = await client.post(
                f"/api/v1/job-discovery-results/{incomplete_result['id']}/draft",
                headers=first_headers,
            )
            incomplete_id = incomplete_draft.json()["id"]
            blocked = await client.post(
                f"/api/v1/job-drafts/{incomplete_id}/confirm", headers=first_headers
            )
            assert blocked.status_code == 409
            updated = await client.patch(
                f"/api/v1/job-drafts/{incomplete_id}",
                headers={**first_headers, "If-Match": "1"},
                json={"raw_description": "Complete description supplied by the user."},
            )
            assert updated.status_code == 200
            assert (
                await client.post(
                    f"/api/v1/job-drafts/{incomplete_id}/confirm", headers=first_headers
                )
            ).status_code == 201

    await session_factory.kw["bind"].dispose()


async def register_and_login(client: AsyncClient, email: str) -> str:
    password = "strong-password"
    registered = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert registered.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert isinstance(token, str)
    return token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
