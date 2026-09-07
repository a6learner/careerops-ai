import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from careerops.api.parse_runs import get_parse_run_dispatcher
from careerops.db.models import ParseRun
from careerops.domain.errors import ParseRunDispatchError
from careerops.domain.parse_runs import ParsedRequirement, ParserOutput, RequirementCategory
from careerops.main import create_app
from careerops.repositories.parse_runs import ParseRunRepository
from careerops.services.parse_run_execution import ParseRunExecutionService
from careerops.services.parse_run_recovery import ParseRunRecoveryService
from careerops.workers.tasks import execute_parse_run_async

pytestmark = pytest.mark.integration


class RecordingDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[UUID] = []

    async def dispatch(self, parse_run_id: UUID) -> None:
        self.dispatched.append(parse_run_id)


class FailingDispatcher:
    async def dispatch(self, parse_run_id: UUID) -> None:
        raise ParseRunDispatchError()


class InvalidParser:
    async def parse(self, input_text: str) -> ParserOutput:
        return ParserOutput(
            model_name="invalid-parser",
            requirements=(
                ParsedRequirement(
                    category=RequirementCategory.MUST_HAVE,
                    text="not grounded",
                    skill_normalized=None,
                    source_span_start=0,
                    source_span_end=3,
                ),
            ),
        )


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_parse_runs_are_idempotent_and_authorized() -> None:
    app = create_app()
    dispatcher = RecordingDispatcher()
    app.dependency_overrides[get_parse_run_dispatcher] = lambda: dispatcher
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
            app.dependency_overrides[get_parse_run_dispatcher] = lambda: FailingDispatcher()
            failed_dispatch = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "dispatch-fail"},
            )
            app.dependency_overrides[get_parse_run_dispatcher] = lambda: dispatcher
            retried_dispatch = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "dispatch-fail"},
            )
            invalid_run = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "invalid-output"},
            )
            async with app.state.session_factory() as execution_session:
                invalid_executed = await ParseRunExecutionService(
                    ParseRunRepository(execution_session),
                    InvalidParser(),
                ).execute(UUID(invalid_run.json()["id"]))
            failed_run = await client.get(
                f"/api/v1/jobs/{job_id}/parse-runs/{invalid_run.json()['id']}",
                headers=auth_header(first_token),
            )
            stale_run = await client.post(
                f"/api/v1/jobs/{job_id}/parse-runs",
                headers={**auth_header(first_token), "Idempotency-Key": "stale-run"},
            )
            stale_run_id = UUID(stale_run.json()["id"])
            async with app.state.session_factory() as stale_session:
                await stale_session.execute(
                    update(ParseRun)
                    .where(ParseRun.id == stale_run_id)
                    .values(
                        status="running",
                        started_at=datetime.now(UTC) - timedelta(minutes=10),
                    )
                )
                await stale_session.commit()
            async with app.state.session_factory() as recovery_session:
                recovery_result = await ParseRunRecoveryService(
                    ParseRunRepository(recovery_session),
                    dispatcher,
                ).recover(datetime.now(UTC) - timedelta(minutes=5), 100)
            recovered_run = await client.get(
                f"/api/v1/jobs/{job_id}/parse-runs/{stale_run_id}",
                headers=auth_header(first_token),
            )
            worker_results = await asyncio.gather(
                execute_parse_run_async(UUID(submitted.json()["id"])),
                execute_parse_run_async(UUID(submitted.json()["id"])),
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
    assert submitted.json()["status"] == "queued"
    assert submitted.json()["model_name"] == "local-fake-parser"
    assert submitted.json()["prompt_version"] == "parse-v1"
    assert submitted.json()["requirements"] == []

    assert repeated.status_code == 202
    assert repeated.json()["id"] == submitted.json()["id"]
    assert repeated.json()["status"] == "queued"

    assert concurrent_first.status_code == 202
    assert concurrent_second.status_code == 202
    assert concurrent_first.json()["id"] == concurrent_second.json()["id"]
    assert concurrent_first.json()["status"] == "queued"

    assert second_job.status_code == 201
    assert scoped_to_second_job.status_code == 202
    assert scoped_to_second_job.json()["job_id"] == second_job.json()["id"]
    assert scoped_to_second_job.json()["id"] != submitted.json()["id"]

    assert updated_job.status_code == 200
    assert conflicting_replay.status_code == 409
    assert conflicting_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    assert oversized_key.status_code == 422
    assert oversized_key.json()["error"]["code"] == "VALIDATION_ERROR"

    assert failed_dispatch.status_code == 503
    assert failed_dispatch.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert retried_dispatch.status_code == 202
    assert retried_dispatch.json()["status"] == "queued"

    assert invalid_executed
    assert failed_run.status_code == 200
    assert failed_run.json()["status"] == "failed"
    assert failed_run.json()["error_code"] == "PARSER_OUTPUT_INVALID"

    assert recovery_result.requeued >= 1
    assert stale_run_id in dispatcher.dispatched
    assert recovered_run.status_code == 200
    assert recovered_run.json()["status"] == "queued"
    assert recovered_run.json()["attempt"] == 2

    assert sorted(worker_results) == [False, True]

    assert fetched.status_code == 200
    assert fetched.json()["id"] == submitted.json()["id"]
    assert fetched.json()["status"] == "succeeded"
    assert len(fetched.json()["requirements"]) == 3
    assert fetched.json()["requirements"][0]["category"] == "must_have"
    assert fetched.json()["requirements"][0]["skill_normalized"] == "python"
    assert fetched.json()["requirements"][0]["source_span_start"] == 0

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
