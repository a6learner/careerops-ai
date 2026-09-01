import pytest
from httpx import ASGITransport, AsyncClient

from careerops.main import create_app


@pytest.mark.asyncio
async def test_healthz_returns_service_status() -> None:
    app = create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "careerops-api"}
    assert "x-request-id" in response.headers
