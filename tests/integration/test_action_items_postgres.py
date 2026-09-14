import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from careerops.core.config import Settings
from careerops.db.models import (
    ActionItem,
    AnalysisRun,
    EvidenceMatch,
    Experience,
    Job,
    JobRequirement,
    ParseRun,
    User,
)
from careerops.db.session import create_session_factory
from careerops.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_action_items_complete_contract_and_preserve_archived_jobs() -> None:
    app = create_app()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            user_id, token = await register_and_login(client, "action-owner")
            _, other_token = await register_and_login(client, "action-other")
            job = await create_job(client, token, "Action Item Job")
            other_job = await create_job(client, token, "Other Job")
            source_ids = await seed_evidence_matches(user_id, UUID(job["id"]))

            missing_key = await client.post(
                "/api/v1/action-items",
                headers=auth_header(token),
                json={"job_id": job["id"], "title": "Manual task"},
            )
            manual = await create_action_item(
                client,
                token,
                "manual-key",
                job["id"],
                "Manual task",
            )
            replay = await create_action_item(
                client,
                token,
                "manual-key",
                job["id"],
                "Manual task",
            )
            changed_replay = await client.post(
                "/api/v1/action-items",
                headers={**auth_header(token), "Idempotency-Key": "manual-key"},
                json={"job_id": job["id"], "title": "Different task"},
            )

            created_from_gaps = []
            for verdict in ("partial", "missing", "insufficient_evidence"):
                created_from_gaps.append(
                    await create_action_item(
                        client,
                        token,
                        f"gap-{verdict}",
                        job["id"],
                        f"Address {verdict}",
                        source_ids[verdict],
                    )
                )
            duplicate_gap = await create_action_item(
                client,
                token,
                "gap-missing-second",
                job["id"],
                "Address missing another way",
                source_ids["missing"],
            )
            matched_source = await client.post(
                "/api/v1/action-items",
                headers={**auth_header(token), "Idempotency-Key": "gap-matched"},
                json={
                    "job_id": job["id"],
                    "title": "Should fail",
                    "source_evidence_match_id": source_ids["matched"],
                },
            )
            wrong_job_source = await client.post(
                "/api/v1/action-items",
                headers={**auth_header(token), "Idempotency-Key": "wrong-job-source"},
                json={
                    "job_id": other_job["id"],
                    "title": "Should also fail",
                    "source_evidence_match_id": source_ids["missing"],
                },
            )

            concurrent = await asyncio.gather(
                *(
                    create_action_item(
                        client,
                        token,
                        "concurrent-key",
                        job["id"],
                        "Concurrent task",
                    )
                    for _ in range(3)
                )
            )
            filtered = await client.get(
                "/api/v1/action-items",
                headers=auth_header(token),
                params={"job_id": job["id"], "status": "todo", "limit": 1},
            )
            next_page = await client.get(
                "/api/v1/action-items",
                headers=auth_header(token),
                params={
                    "job_id": job["id"],
                    "status": "todo",
                    "limit": 1,
                    "cursor": filtered.json()["next_cursor"],
                },
            )
            other_user_list = await client.get(
                "/api/v1/action-items",
                headers=auth_header(other_token),
            )
            unauthorized_update = await client.patch(
                f"/api/v1/action-items/{manual['id']}",
                headers={**auth_header(other_token), "If-Match": "1"},
                json={"status": "doing"},
            )
            missing_if_match = await client.patch(
                f"/api/v1/action-items/{manual['id']}",
                headers=auth_header(token),
                json={"status": "doing"},
            )
            stale_update = await client.patch(
                f"/api/v1/action-items/{manual['id']}",
                headers={**auth_header(token), "If-Match": "99"},
                json={"status": "doing"},
            )
            updated = await client.patch(
                f"/api/v1/action-items/{manual['id']}",
                headers={**auth_header(token), "If-Match": "1"},
                json={"title": "Updated manual task", "status": "doing"},
            )
            archived = await client.delete(
                f"/api/v1/jobs/{job['id']}",
                headers=auth_header(token),
            )
            archived_list = await client.get(
                "/api/v1/action-items",
                headers=auth_header(token),
                params={"job_id": job["id"]},
            )
            updated_after_archive = await client.patch(
                f"/api/v1/action-items/{manual['id']}",
                headers={**auth_header(token), "If-Match": "2"},
                json={"status": "done"},
            )
            new_for_archived_job = await client.post(
                "/api/v1/action-items",
                headers={**auth_header(token), "Idempotency-Key": "after-archive"},
                json={"job_id": job["id"], "title": "Should not be created"},
            )
            replay_after_archive = await create_action_item(
                client,
                token,
                "manual-key",
                job["id"],
                "Manual task",
            )

    assert missing_key.status_code == 428
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert manual["status"] == "todo"
    assert manual["source_evidence_match_id"] is None
    assert replay["id"] == manual["id"]
    assert changed_replay.status_code == 409
    assert changed_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    assert {item["source_evidence_match_id"] for item in created_from_gaps} == {
        source_ids["partial"],
        source_ids["missing"],
        source_ids["insufficient_evidence"],
    }
    assert duplicate_gap["id"] != created_from_gaps[1]["id"]
    assert duplicate_gap["source_evidence_match_id"] == source_ids["missing"]
    assert matched_source.status_code == 409
    assert matched_source.json()["error"]["code"] == "ACTION_ITEM_SOURCE_NOT_ACTIONABLE"
    assert wrong_job_source.status_code == 404
    assert wrong_job_source.json()["error"]["code"] == "ACTION_ITEM_SOURCE_NOT_FOUND"

    assert len({item["id"] for item in concurrent}) == 1
    assert filtered.status_code == 200
    assert len(filtered.json()["items"]) == 1
    assert filtered.json()["next_cursor"] is not None
    assert next_page.status_code == 200
    assert len(next_page.json()["items"]) == 1
    assert other_user_list.json()["items"] == []
    assert unauthorized_update.status_code == 404
    assert unauthorized_update.json()["error"]["code"] == "ACTION_ITEM_NOT_FOUND"
    assert missing_if_match.status_code == 428
    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "ACTION_ITEM_VERSION_CONFLICT"
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated manual task"
    assert updated.json()["status"] == "doing"
    assert updated.json()["version"] == 2

    assert archived.status_code == 204
    assert archived_list.status_code == 200
    assert archived_list.json()["items"]
    assert all(item["job_is_archived"] for item in archived_list.json()["items"])
    assert updated_after_archive.status_code == 200
    assert updated_after_archive.json()["status"] == "done"
    assert updated_after_archive.json()["job_is_archived"] is True
    assert new_for_archived_job.status_code == 404
    assert new_for_archived_job.json()["error"]["code"] == "JOB_NOT_FOUND"
    assert replay_after_archive["id"] == manual["id"]
    assert replay_after_archive["job_is_archived"] is True


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local PostgreSQL container",
)
@pytest.mark.asyncio
async def test_action_item_database_constraints_reject_invalid_rows() -> None:
    session_factory = create_session_factory(Settings().database_url)
    user_id = uuid4()
    job_id = uuid4()
    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=f"action-constraints-{uuid4()}@example.com",
                password_hash="x",
            )
        )
        await setup_session.flush()
        setup_session.add(
            Job(
                id=job_id,
                user_id=user_id,
                company="Example",
                title="Backend Intern",
                raw_description="Build APIs.",
                description_hash="a" * 64,
                status="saved",
                version=1,
            )
        )
        await setup_session.commit()

    invalid_values = (
        {"title": "Valid", "status": "blocked", "version": 1},
        {"title": "   ", "status": "todo", "version": 1},
        {"title": "Valid", "status": "todo", "version": 0},
    )
    for index, values in enumerate(invalid_values):
        async with session_factory() as session:
            session.add(
                ActionItem(
                    user_id=user_id,
                    job_id=job_id,
                    idempotency_key=f"invalid-{index}",
                    request_fingerprint="b" * 64,
                    **values,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

    async with session_factory() as first_session:
        first_session.add(
            ActionItem(
                user_id=user_id,
                job_id=job_id,
                title="Valid",
                status="todo",
                version=1,
                idempotency_key="duplicate",
                request_fingerprint="c" * 64,
            )
        )
        await first_session.commit()
    async with session_factory() as duplicate_session:
        duplicate_session.add(
            ActionItem(
                user_id=user_id,
                job_id=job_id,
                title="Another",
                status="todo",
                version=1,
                idempotency_key="duplicate",
                request_fingerprint="d" * 64,
            )
        )
        with pytest.raises(IntegrityError):
            await duplicate_session.commit()
        await duplicate_session.rollback()

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(delete(ActionItem).where(ActionItem.user_id == user_id))
        user = await cleanup_session.get(User, user_id)
        assert user is not None
        await cleanup_session.delete(user)
        await cleanup_session.commit()
    await session_factory.kw["bind"].dispose()


async def seed_evidence_matches(user_id: UUID, job_id: UUID) -> dict[str, str]:
    session_factory = create_session_factory(Settings().database_url)
    parse_run_id = uuid4()
    analysis_run_id = uuid4()
    experience_id = uuid4()
    now = datetime.now(UTC)
    requirement_ids = {
        verdict: uuid4() for verdict in ("partial", "missing", "insufficient_evidence", "matched")
    }
    evidence_ids = {verdict: uuid4() for verdict in requirement_ids}

    async with session_factory() as session:
        session.add(
            Experience(
                id=experience_id,
                user_id=user_id,
                title="CareerOps AI",
                kind="project",
                description="Built reliable APIs.",
                skills=["Python"],
                version=1,
                content_hash="e" * 64,
            )
        )
        session.add(
            ParseRun(
                id=parse_run_id,
                user_id=user_id,
                job_id=job_id,
                status="succeeded",
                idempotency_key=f"parse-{uuid4()}",
                input_fingerprint="f" * 64,
                input_text="Python required.",
                model_name="fake",
                prompt_version="parse-v2",
                attempt=1,
                started_at=now,
                finished_at=now,
            )
        )
        await session.flush()
        session.add_all(
            JobRequirement(
                id=requirement_id,
                job_id=job_id,
                parse_run_id=parse_run_id,
                category="must_have",
                text=f"{verdict} requirement",
            )
            for verdict, requirement_id in requirement_ids.items()
        )
        await session.flush()
        session.add(
            AnalysisRun(
                id=analysis_run_id,
                user_id=user_id,
                job_id=job_id,
                parse_run_id=parse_run_id,
                status="succeeded",
                idempotency_key=f"analysis-{uuid4()}",
                input_fingerprint="a" * 64,
                model_name="fake-evidence-matcher",
                prompt_version="match-v1",
                attempt=1,
                started_at=now,
                finished_at=now,
            )
        )
        await session.flush()
        for verdict, evidence_id in evidence_ids.items():
            positive = verdict in {"partial", "matched"}
            session.add(
                EvidenceMatch(
                    id=evidence_id,
                    analysis_run_id=analysis_run_id,
                    requirement_id=requirement_ids[verdict],
                    experience_id=experience_id if positive else None,
                    experience_version=1 if positive else None,
                    verdict=verdict,
                    quote="Built reliable APIs." if positive else None,
                    quote_valid=positive,
                    confidence=None,
                )
            )
        await session.commit()
    await session_factory.kw["bind"].dispose()
    return {verdict: str(evidence_id) for verdict, evidence_id in evidence_ids.items()}


async def register_and_login(
    client: AsyncClient,
    label: str,
) -> tuple[UUID, str]:
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


async def create_job(client: AsyncClient, token: str, title: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/jobs",
        headers=auth_header(token),
        json={
            "company": "Example",
            "title": title,
            "raw_description": "Build reliable APIs with Python.",
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert isinstance(result, dict)
    return result


async def create_action_item(
    client: AsyncClient,
    token: str,
    key: str,
    job_id: object,
    title: str,
    source_evidence_match_id: str | None = None,
) -> dict[str, object]:
    payload = {"job_id": job_id, "title": title}
    if source_evidence_match_id is not None:
        payload["source_evidence_match_id"] = source_evidence_match_id
    response = await client.post(
        "/api/v1/action-items",
        headers={**auth_header(token), "Idempotency-Key": key},
        json=payload,
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert isinstance(result, dict)
    return result


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
