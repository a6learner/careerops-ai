from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from careerops.api import action_items
from careerops.api.dependencies import get_current_user
from careerops.db.session import get_session
from careerops.domain.action_items import ActionItemCreate, ActionItemRecord, ActionItemStatus
from careerops.domain.errors import (
    ActionItemSourceNotActionableError,
    ActionItemSourceNotFoundError,
)
from careerops.domain.users import UserAccount
from careerops.main import create_app


class ActionItemCreateService:
    def __init__(self, result: ActionItemRecord | Exception) -> None:
        self.result = result

    async def create_action_item(self, payload: ActionItemCreate) -> ActionItemRecord:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def build_test_app() -> tuple[FastAPI, UserAccount]:
    app = create_app()
    user = UserAccount(
        id=uuid4(),
        email="student@example.com",
        created_at=datetime.now(UTC),
    )

    async def current_user() -> UserAccount:
        return user

    async def fake_session() -> None:
        return None

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_session] = fake_session
    return app, user


@pytest.mark.asyncio
async def test_action_item_create_requires_idempotency_key() -> None:
    app, _ = build_test_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/action-items",
            json={"job_id": str(uuid4()), "title": "Practice APIs"},
        )

    assert response.status_code == 428
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (ActionItemSourceNotFoundError(), 404, "ACTION_ITEM_SOURCE_NOT_FOUND"),
        (
            ActionItemSourceNotActionableError(),
            409,
            "ACTION_ITEM_SOURCE_NOT_ACTIONABLE",
        ),
    ],
)
@pytest.mark.asyncio
async def test_action_item_source_errors_use_project_contract(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    app, _ = build_test_app()
    service = ActionItemCreateService(error)
    monkeypatch.setattr(action_items, "build_action_item_service", lambda session: service)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/action-items",
            headers={"Idempotency-Key": "item-key"},
            json={
                "job_id": str(uuid4()),
                "title": "Practice APIs",
                "source_evidence_match_id": str(uuid4()),
            },
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


@pytest.mark.asyncio
async def test_action_item_create_returns_archived_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, user = build_test_app()
    now = datetime.now(UTC)
    item = ActionItemRecord(
        id=uuid4(),
        user_id=user.id,
        job_id=uuid4(),
        source_evidence_match_id=None,
        title="Practice APIs",
        status=ActionItemStatus.TODO,
        version=1,
        idempotency_key="item-key",
        request_fingerprint="a" * 64,
        job_is_archived=True,
        created_at=now,
        updated_at=now,
    )
    service = ActionItemCreateService(item)
    monkeypatch.setattr(action_items, "build_action_item_service", lambda session: service)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/action-items",
            headers={"Idempotency-Key": "item-key"},
            json={"job_id": str(item.job_id), "title": item.title},
        )

    assert response.status_code == 201
    assert response.json()["job_is_archived"] is True
    assert response.json()["status"] == "todo"
