import logging

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.main import create_app


class StaticReadinessChecker:
    def __init__(self, ready: bool) -> None:
        self._ready = ready

    async def is_ready(self) -> bool:
        return self._ready


@pytest.mark.asyncio
async def test_healthz_returns_service_status() -> None:
    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "careerops-api"}
    assert "x-request-id" in response.headers


@pytest.mark.parametrize(
    ("database_ready", "redis_ready", "expected_status"),
    [
        (True, True, 200),
        (False, True, 503),
        (True, False, 503),
        (False, False, 503),
    ],
)
@pytest.mark.asyncio
async def test_readyz_requires_database_and_redis(
    database_ready: bool,
    redis_ready: bool,
    expected_status: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app()
    app.state.db_checker = StaticReadinessChecker(database_ready)
    app.state.redis_checker = StaticReadinessChecker(redis_ready)

    with caplog.at_level(logging.WARNING, logger="careerops.api.routes"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/readyz")

    expected_ready = database_ready and redis_ready
    assert response.status_code == expected_status
    assert response.json() == {
        "status": "ready" if expected_ready else "not_ready",
        "database": database_ready,
        "redis": redis_ready,
    }
    failure_records = [
        record for record in caplog.records if record.getMessage() == "readiness_check_failed"
    ]
    assert len(failure_records) == (0 if expected_ready else 1)
    if failure_records:
        assert failure_records[0].database_ready is database_ready
        assert failure_records[0].redis_ready is redis_ready
        assert failure_records[0].request_id == response.headers["x-request-id"]
