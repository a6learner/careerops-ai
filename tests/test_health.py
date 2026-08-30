from fastapi.testclient import TestClient

from careerops.main import create_app


def test_healthz_returns_service_status() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "careerops-api"}
    assert "x-request-id" in response.headers
