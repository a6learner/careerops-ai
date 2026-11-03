import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from careerops.core.config import get_settings
from careerops.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
        reason="requires local PostgreSQL and Redis containers",
    ),
]


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_latest_parse_run_orders_by_creation_and_is_owner_scoped() -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            _, token = await register_and_login(client, "latest-owner")
            _, other_token = await register_and_login(client, "latest-other")
            job = await create_job(client, token, title="Latest Job")

            before_any = await client.get(
                f"/api/v1/jobs/{job['id']}/parse-runs/latest",
                headers=auth_header(token),
            )
            await submit_parse_run(client, token, job["id"])
            second = await submit_parse_run(client, token, job["id"])
            latest = await client.get(
                f"/api/v1/jobs/{job['id']}/parse-runs/latest",
                headers=auth_header(token),
            )
            cross_user = await client.get(
                f"/api/v1/jobs/{job['id']}/parse-runs/latest",
                headers=auth_header(other_token),
            )
            analysis_before_any = await client.get(
                f"/api/v1/jobs/{job['id']}/analysis-runs/latest",
                headers=auth_header(token),
                params={"parse_run_id": second["id"]},
            )
            analysis_cross_user = await client.get(
                f"/api/v1/jobs/{job['id']}/analysis-runs/latest",
                headers=auth_header(other_token),
                params={"parse_run_id": second["id"]},
            )
            analysis_missing_param = await client.get(
                f"/api/v1/jobs/{job['id']}/analysis-runs/latest",
                headers=auth_header(token),
            )

    assert before_any.status_code == 404
    assert before_any.json()["error"]["code"] == "PARSE_RUN_NOT_FOUND"
    assert latest.status_code == 200
    assert latest.json()["id"] == second["id"]
    assert cross_user.status_code == 404
    assert cross_user.json()["error"]["code"] == "JOB_NOT_FOUND"
    assert analysis_before_any.status_code == 404
    assert analysis_before_any.json()["error"]["code"] == "ANALYSIS_RUN_NOT_FOUND"
    assert analysis_cross_user.status_code == 404
    assert analysis_cross_user.json()["error"]["code"] == "JOB_NOT_FOUND"
    assert analysis_missing_param.status_code == 422


@pytest.mark.asyncio
async def test_dashboard_focus_filters_closed_past_archived_and_foreign_rows() -> None:
    today = datetime.now(UTC).date()
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            _, token = await register_and_login(client, "focus-owner")
            _, other_token = await register_and_login(client, "focus-other")
            soon = await create_job(client, token, "Soon", deadline=today + timedelta(days=2))
            later = await create_job(client, token, "Later", deadline=today + timedelta(days=9))
            await create_job(client, token, "Past", deadline=today - timedelta(days=1))
            await create_job(
                client, token, "Rejected", deadline=today + timedelta(days=1), status="rejected"
            )
            archived = await create_job(client, token, "Archived", deadline=today)
            await create_job(client, other_token, "Foreign", deadline=today)
            todo = await create_action_item(client, token, soon["id"], "Todo task")
            doing = await create_action_item(client, token, later["id"], "Doing task")
            done = await create_action_item(client, token, later["id"], "Done task")
            await update_action_item(client, token, doing["id"], "doing")
            await update_action_item(client, token, done["id"], "done")
            await create_action_item(client, token, archived["id"], "Archived task")
            deleted = await client.delete(
                f"/api/v1/jobs/{archived['id']}", headers=auth_header(token)
            )

            focus = await client.get("/api/v1/dashboard/focus", headers=auth_header(token))

    assert deleted.status_code == 204
    assert focus.status_code == 200
    body = focus.json()
    assert date.fromisoformat(body["today"]) == today
    assert [job["title"] for job in body["upcoming_deadlines"]] == ["Soon", "Later"]
    recent_titles = [job["title"] for job in body["recent_jobs"]]
    assert "Archived" not in recent_titles
    assert "Foreign" not in recent_titles
    assert [item["title"] for item in body["open_action_items"]] == ["Doing task", "Todo task"]
    assert body["open_action_items"][1]["job_title"] == "Soon"
    assert todo["id"] == body["open_action_items"][1]["id"]


async def register_and_login(client: AsyncClient, label: str) -> tuple[UUID, str]:
    email = f"{label}-{uuid4()}@example.com"
    password = "strong-password"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert registered.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return UUID(registered.json()["id"]), login.json()["access_token"]


async def create_job(
    client: AsyncClient,
    token: str,
    title: str,
    deadline: date | None = None,
    status: str = "saved",
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/jobs",
        headers=auth_header(token),
        json={
            "company": "Example",
            "title": title,
            "raw_description": "Build reliable APIs with Python and PostgreSQL.",
            "status": status,
            "deadline": deadline.isoformat() if deadline else None,
        },
    )
    assert response.status_code == 201
    return dict(response.json())


async def submit_parse_run(client: AsyncClient, token: str, job_id: str) -> dict[str, str]:
    response = await client.post(
        f"/api/v1/jobs/{job_id}/parse-runs",
        headers={**auth_header(token), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 202
    return dict(response.json())


async def create_action_item(
    client: AsyncClient, token: str, job_id: str, title: str
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/action-items",
        headers={**auth_header(token), "Idempotency-Key": str(uuid4())},
        json={"job_id": job_id, "title": title},
    )
    assert response.status_code == 201
    return dict(response.json())


async def update_action_item(client: AsyncClient, token: str, item_id: str, status: str) -> None:
    response = await client.patch(
        f"/api/v1/action-items/{item_id}",
        headers={**auth_header(token), "If-Match": "1"},
        json={"status": status},
    )
    assert response.status_code == 200


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
