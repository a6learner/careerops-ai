import asyncio
import os
from collections.abc import Iterator
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops.cache.dashboard import cache_key
from careerops.core.config import get_settings
from careerops.db.models import ActionItem
from careerops.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL and Redis containers",
)
@pytest.mark.asyncio
async def test_dashboard_summary_cache_invalidation_and_archived_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAREEROPS_REDIS_URL", "redis://127.0.0.1:6379/0")
    get_settings.cache_clear()
    app = create_app()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            user_id, token = await register_and_login(client, "dashboard-owner")
            _, other_token = await register_and_login(client, "dashboard-other")
            saved_job = await create_job(client, token, "Saved Job", "saved")
            archived_job = await create_job(client, token, "Applied Job", "applied")
            other_job = await create_job(client, other_token, "Other Job", "saved")
            active_item = await create_action_item(client, token, saved_job["id"], "Active task")
            await create_action_item(client, token, archived_job["id"], "Archived task")
            session_factory = cast(
                async_sessionmaker[AsyncSession],
                app.state.session_factory,
            )
            async with session_factory() as session:
                session.add(
                    ActionItem(
                        user_id=user_id,
                        job_id=UUID(str(other_job["id"])),
                        title="Cross-owner corrupt task",
                        status="todo",
                        version=1,
                        idempotency_key=str(uuid4()),
                        request_fingerprint="0" * 64,
                    )
                )
                await session.commit()

            first = await client.get("/api/v1/dashboard/summary", headers=auth_header(token))
            second = await client.get("/api/v1/dashboard/summary", headers=auth_header(token))
            other = await client.get(
                "/api/v1/dashboard/summary",
                headers=auth_header(other_token),
            )

            redis_client = cast(Redis, app.state.redis_client)
            owner_key = cache_key(user_id)
            assert await redis_client.get(owner_key) is not None
            ttl = await redis_client.ttl(owner_key)

            job_update = await client.patch(
                f"/api/v1/jobs/{saved_job['id']}",
                headers={**auth_header(token), "If-Match": "1"},
                json={"status": "interview"},
            )
            assert await redis_client.get(owner_key) is None
            after_job_update = await client.get(
                "/api/v1/dashboard/summary",
                headers=auth_header(token),
            )

            item_update = await client.patch(
                f"/api/v1/action-items/{active_item['id']}",
                headers={**auth_header(token), "If-Match": "1"},
                json={"status": "doing"},
            )
            assert await redis_client.get(owner_key) is None
            after_item_update = await client.get(
                "/api/v1/dashboard/summary",
                headers=auth_header(token),
            )

            archived = await client.delete(
                f"/api/v1/jobs/{archived_job['id']}",
                headers=auth_header(token),
            )
            assert await redis_client.get(owner_key) is None
            concurrent = await asyncio.gather(
                *(
                    client.get("/api/v1/dashboard/summary", headers=auth_header(token))
                    for _ in range(3)
                )
            )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["jobs"] == {
        "total": 2,
        "saved": 1,
        "preparing": 0,
        "applied": 1,
        "interview": 0,
        "offer": 0,
        "rejected": 0,
        "withdrawn": 0,
    }
    assert first.json()["action_items"] == {"total": 2, "todo": 2, "doing": 0, "done": 0}
    assert 0 < ttl <= 30
    assert other.status_code == 200
    assert other.json()["jobs"]["total"] == 1
    assert other.json()["action_items"]["total"] == 0

    assert job_update.status_code == 200
    assert after_job_update.json()["jobs"]["interview"] == 1
    assert after_job_update.json()["jobs"]["saved"] == 0
    assert item_update.status_code == 200
    assert after_item_update.json()["action_items"] == {
        "total": 2,
        "todo": 1,
        "doing": 1,
        "done": 0,
    }
    assert archived.status_code == 204
    assert all(response.status_code == 200 for response in concurrent)
    assert all(response.json()["jobs"]["total"] == 1 for response in concurrent)
    assert all(response.json()["action_items"]["total"] == 1 for response in concurrent)


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_dashboard_falls_back_to_postgres_when_redis_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAREEROPS_REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    app = create_app()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            _, token = await register_and_login(client, "dashboard-cache-down")
            response = await client.get(
                "/api/v1/dashboard/summary",
                headers=auth_header(token),
            )

    assert response.status_code == 200
    assert response.json()["jobs"]["total"] == 0
    assert response.json()["action_items"]["total"] == 0


async def register_and_login(client: AsyncClient, label: str) -> tuple[UUID, str]:
    email = f"{label}-{uuid4()}@example.com"
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
    return UUID(registered.json()["id"]), login.json()["access_token"]


async def create_job(
    client: AsyncClient,
    token: str,
    title: str,
    status: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/jobs",
        headers=auth_header(token),
        json={
            "company": "Example",
            "title": title,
            "raw_description": "Build reliable APIs.",
            "status": status,
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert isinstance(result, dict)
    return result


async def create_action_item(
    client: AsyncClient,
    token: str,
    job_id: object,
    title: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/action-items",
        headers={**auth_header(token), "Idempotency-Key": str(uuid4())},
        json={"job_id": job_id, "title": title},
    )
    assert response.status_code == 201
    result = response.json()
    assert isinstance(result, dict)
    return result


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
