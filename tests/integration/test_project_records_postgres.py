import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops.core.config import Settings
from careerops.db.models import ProjectCheckpoint, User
from careerops.db.session import create_session_factory
from careerops.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("CAREEROPS_RUN_INTEGRATION") != "1", reason="requires isolated PostgreSQL"
    ),
]


def packet() -> dict[str, object]:
    return {
        "title": "Prevent duplicate writes",
        "objective": "Make retries safe",
        "changes": "Add a unique key and compare request hashes",
        "host": "synthetic-test",
        "verification": "Client supplied fixture, not a server-certified test result.",
        "sources": [
            {
                "kind": "repository_excerpt",
                "locator": "src/example.py",
                "content": "unique key prevents duplicate writes",
                "quote": "unique key",
            }
        ],
    }


async def login(client: AsyncClient) -> tuple[UUID, dict[str, str]]:
    credentials = {"email": f"record-{uuid4()}@example.com", "password": "StrongPassword123!"}
    registered = await client.post("/api/v1/auth/register", json=credentials)
    assert registered.status_code == 201
    token = await client.post("/api/v1/auth/login", json=credentials)
    assert token.status_code == 200
    return UUID(registered.json()["id"]), {
        "Authorization": f"Bearer {token.json()['access_token']}"
    }


@pytest.mark.asyncio
async def test_records_contract_concurrency_authorization_and_withdrawal() -> None:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c,
    ):
        owner, headers = await login(c)
        other, other_headers = await login(c)
        try:
            assert (await c.get("/api/v1/projects")).status_code == 401
            project_payload = {"name": "Career project", "goal": "Demonstrate reliability"}
            assert (
                await c.post("/api/v1/projects", json=project_payload, headers=headers)
            ).status_code == 428
            project_headers = {**headers, "Idempotency-Key": "project-key"}
            projects = await asyncio.gather(
                *[
                    c.post("/api/v1/projects", json=project_payload, headers=project_headers)
                    for _ in range(3)
                ]
            )
            assert {p.status_code for p in projects} == {201}
            project = projects[0].json()
            assert len({p.json()["id"] for p in projects}) == 1
            project_url = f"/api/v1/projects/{project['id']}"
            assert (
                await c.post(
                    "/api/v1/projects",
                    headers=project_headers,
                    json={**project_payload, "goal": "Changed"},
                )
            ).status_code == 409
            assert (await c.get(project_url, headers=other_headers)).status_code == 404
            assert (await c.get("/api/v1/projects", headers=other_headers)).json()["items"] == []
            url = project_url + "/checkpoints"
            record_headers = {**headers, "Idempotency-Key": "record-key"}
            responses = await asyncio.gather(
                *[c.post(url, json=packet(), headers=record_headers) for _ in range(3)]
            )
            assert {r.status_code for r in responses} == {201}
            assert len({r.json()["id"] for r in responses}) == 1
            record = responses[0].json()
            assert record["status"] == "draft" and record["version"] == 1
            assert len(record["content_sha256"]) == 64
            detail = url + "/" + record["id"]
            assert (
                await c.post(url, json={**packet(), "title": "Changed"}, headers=record_headers)
            ).status_code == 409
            for path in (url, detail):
                assert (await c.get(path, headers=other_headers)).status_code == 404
            assert (
                await c.post(
                    url,
                    json=packet(),
                    headers={
                        **other_headers,
                        "Idempotency-Key": "stolen",
                    },
                )
            ).status_code == 404
            assert (
                await c.patch(
                    detail + "/review",
                    headers={
                        **other_headers,
                        "If-Match": "1",
                    },
                    json={"status": "confirmed", "contribution_note": "Mine"},
                )
            ).status_code == 404
            confirmed_search = await c.get(url, headers=headers, params={"status": "confirmed"})
            assert confirmed_search.json()["items"] == []
            review_url = detail + "/review"
            confirm = {"status": "confirmed", "contribution_note": "I designed the invariant."}
            assert (await c.patch(review_url, headers=headers, json=confirm)).status_code == 428
            assert (
                await c.patch(
                    review_url,
                    headers={**headers, "If-Match": "1"},
                    json={"status": "confirmed"},
                )
            ).status_code == 422
            assert (
                await c.patch(review_url, headers={**headers, "If-Match": "9"}, json=confirm)
            ).status_code == 409
            oversized_precondition = await c.patch(
                review_url, headers={**headers, "If-Match": "9" * 5000}, json=confirm
            )
            assert oversized_precondition.status_code == 428
            assert oversized_precondition.json()["error"]["code"] == "IF_MATCH_REQUIRED"
            reviewed = await asyncio.gather(
                *[
                    c.patch(review_url, headers={**headers, "If-Match": "1"}, json=confirm)
                    for _ in range(2)
                ]
            )
            assert {r.status_code for r in reviewed} == {200}
            assert {r.json()["version"] for r in reviewed} == {2}
            found = await c.get(url, headers=headers, params={"status": "confirmed", "q": "unique"})
            assert len(found.json()["items"]) == 1
            assert (await c.get(url, headers=headers, params={"q": "%"})).json()["items"] == []
            assert (await c.get(url, headers=headers, params={"cursor": "!!!"})).status_code == 422
            withdrawal = {"status": "withdrawn"}
            assert (
                await c.patch(review_url, headers={**headers, "If-Match": "1"}, json=withdrawal)
            ).status_code == 409
            withdrawn = await c.patch(
                review_url, headers={**headers, "If-Match": "2"}, json=withdrawal
            )
            assert withdrawn.status_code == 200 and withdrawn.json()["version"] == 3
            assert withdrawn.json()["contribution_note"] == confirm["contribution_note"]
            replay = await c.post(url, headers=record_headers, json=packet())
            assert replay.status_code == 201 and replay.json()["status"] == "withdrawn"
            assert (
                await c.patch(review_url, headers={**headers, "If-Match": "3"}, json=confirm)
            ).status_code == 409
            assert (await c.get(url, headers=headers, params={"status": "confirmed"})).json()[
                "items"
            ] == []
            for n in range(2):
                result = await c.post(
                    url,
                    json=packet(),
                    headers={
                        **headers,
                        "Idempotency-Key": f"page-{n}",
                    },
                )
                assert result.status_code == 201
            first = (await c.get(url, headers=headers, params={"limit": 1})).json()
            second = (
                await c.get(
                    url,
                    headers=headers,
                    params={
                        "limit": 1,
                        "cursor": first["next_cursor"],
                    },
                )
            ).json()
            assert first["items"][0]["id"] != second["items"][0]["id"]
            competing_record = await c.post(
                url, json=packet(), headers={**headers, "Idempotency-Key": "competing-review"}
            )
            competing_url = url + "/" + competing_record.json()["id"] + "/review"
            competing = await asyncio.gather(
                *[
                    c.patch(
                        competing_url,
                        headers={**headers, "If-Match": "1"},
                        json={"status": "confirmed", "contribution_note": note},
                    )
                    for note in ("I designed it.", "I only reviewed it.")
                ]
            )
            assert sorted(r.status_code for r in competing) == [200, 409]
            assert (await c.get("/api/v1/experiences", headers=headers)).json()["items"] == []
            await assert_ddl_guards(
                owner,
                other,
                UUID(project["id"]),
                UUID(record["id"]),
                UUID(competing_record.json()["id"]),
            )
        finally:
            factory = app.state.session_factory
            async with factory() as session:
                await session.execute(delete(User).where(User.id.in_([owner, other])))
                await session.commit()


async def assert_ddl_guards(
    owner: UUID, other: UUID, project: UUID, record: UUID, confirmed_record: UUID
) -> None:
    factory = create_session_factory(Settings().database_url)
    try:
        async with factory() as session:
            # Even bypassing the API cannot mutate a withdrawn source snapshot.
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(ProjectCheckpoint)
                    .where(ProjectCheckpoint.id == record)
                    .values(payload=packet())
                )
            await session.rollback()
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(ProjectCheckpoint)
                    .where(ProjectCheckpoint.id == confirmed_record)
                    .values(
                        status="withdrawn",
                        version=ProjectCheckpoint.version + 1,
                        reviewed_at=func.now(),
                        contribution_note="Rewritten during withdrawal",
                    )
                )
            await session.rollback()
            unchanged = await session.get(ProjectCheckpoint, confirmed_record)
            assert unchanged is not None
            assert unchanged.status == "confirmed"
            assert unchanged.version == 2
            assert unchanged.contribution_note in {"I designed it.", "I only reviewed it."}
            for bad_payload, user in [
                ({**packet(), "sources": []}, owner),
                (
                    {
                        **packet(),
                        "sources": [
                            {
                                "kind": "user_note",
                                "locator": "note",
                                "content": "actual",
                                "quote": "fabricated",
                            }
                        ],
                    },
                    owner,
                ),
                (packet(), other),
            ]:
                with pytest.raises(IntegrityError):
                    await session.execute(
                        insert(ProjectCheckpoint).values(
                            id=uuid4(),
                            user_id=user,
                            project_id=project,
                            idempotency_key=str(uuid4()),
                            content_sha256="a" * 64,
                            payload=bad_payload,
                        )
                    )
                await session.rollback()
            count = (
                await session.scalars(
                    select(ProjectCheckpoint).where(ProjectCheckpoint.user_id == owner)
                )
            ).all()
            assert len(count) == 4
    finally:
        engine = factory.kw["bind"]
        assert isinstance(engine, AsyncEngine)
        await engine.dispose()
