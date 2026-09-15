from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from careerops.api.dashboard import to_response
from careerops.db.session import get_session
from careerops.domain.dashboard import (
    ActionItemStatusCounts,
    DashboardSummary,
    JobStatusCounts,
)
from careerops.main import create_app


def test_dashboard_response_has_fixed_zero_value_statuses() -> None:
    response = to_response(
        DashboardSummary(
            generated_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
            jobs=JobStatusCounts(
                total=0,
                saved=0,
                preparing=0,
                applied=0,
                interview=0,
                offer=0,
                rejected=0,
                withdrawn=0,
            ),
            action_items=ActionItemStatusCounts(total=0, todo=0, doing=0, done=0),
        )
    )

    assert response.model_dump(mode="json") == {
        "generated_at": "2026-09-13T12:00:00Z",
        "jobs": {
            "total": 0,
            "saved": 0,
            "preparing": 0,
            "applied": 0,
            "interview": 0,
            "offer": 0,
            "rejected": 0,
            "withdrawn": 0,
        },
        "action_items": {"total": 0, "todo": 0, "doing": 0, "done": 0},
    }


@pytest.mark.asyncio
async def test_dashboard_summary_requires_authentication() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = empty_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_MISSING"


async def empty_session() -> AsyncIterator[AsyncSession]:
    yield cast(AsyncSession, object())
