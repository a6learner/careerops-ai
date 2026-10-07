import os

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL and Redis containers",
)
@pytest.mark.asyncio
async def test_readyz_reports_database_and_redis_ready() -> None:
    app = create_app()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": True,
        "redis": True,
    }
