from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from careerops.api import analysis_runs
from careerops.api.dependencies import get_current_user
from careerops.db.session import get_session
from careerops.domain.errors import (
    AnalysisRateLimitExceededError,
    AnalysisRateLimitUnavailableError,
    NoActiveExperiencesError,
    ParseRunNotReadyError,
)
from careerops.domain.users import UserAccount
from careerops.main import create_app


class RejectingAnalysisRunService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def submit_analysis_run(
        self,
        user_id: UUID,
        job_id: UUID,
        parse_run_id: UUID,
        idempotency_key: str,
        request_id: str,
    ) -> None:
        raise self.error


def build_test_app() -> FastAPI:
    app = create_app()

    async def current_user() -> UserAccount:
        return UserAccount(
            id=uuid4(),
            email="student@example.com",
            created_at=datetime.now(UTC),
        )

    async def fake_session() -> None:
        return None

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_session] = fake_session
    return app


@pytest.mark.asyncio
async def test_analysis_submit_requires_idempotency_key() -> None:
    app = build_test_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/jobs/{uuid4()}/analysis-runs",
            json={"parse_run_id": str(uuid4())},
        )

    assert response.status_code == 428
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ParseRunNotReadyError(), "PARSE_RUN_NOT_READY"),
        (NoActiveExperiencesError(), "NO_ACTIVE_EXPERIENCES"),
    ],
)
@pytest.mark.asyncio
async def test_analysis_precondition_errors_use_conflict_contract(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    code: str,
) -> None:
    app = build_test_app()
    service = RejectingAnalysisRunService(error)
    monkeypatch.setattr(
        analysis_runs,
        "build_analysis_run_service",
        lambda session, dispatcher, rate_limiter: service,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/jobs/{uuid4()}/analysis-runs",
            headers={"Idempotency-Key": "analysis-key"},
            json={"parse_run_id": str(uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


@pytest.mark.asyncio
async def test_analysis_rate_limit_error_includes_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = build_test_app()
    service = RejectingAnalysisRunService(AnalysisRateLimitExceededError(43))
    monkeypatch.setattr(
        analysis_runs,
        "build_analysis_run_service",
        lambda session, dispatcher, rate_limiter: service,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/jobs/{uuid4()}/analysis-runs",
            headers={"Idempotency-Key": "analysis-key"},
            json={"parse_run_id": str(uuid4())},
        )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "43"
    assert response.json()["error"]["code"] == "ANALYSIS_RATE_LIMITED"
    assert response.json()["error"]["details"] == {"retry_after_seconds": 43}


@pytest.mark.asyncio
async def test_analysis_rate_limiter_unavailable_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = build_test_app()
    service = RejectingAnalysisRunService(AnalysisRateLimitUnavailableError())
    monkeypatch.setattr(
        analysis_runs,
        "build_analysis_run_service",
        lambda session, dispatcher, rate_limiter: service,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/jobs/{uuid4()}/analysis-runs",
            headers={"Idempotency-Key": "analysis-key"},
            json={"parse_run_id": str(uuid4())},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
