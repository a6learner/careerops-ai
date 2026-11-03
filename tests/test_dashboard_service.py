from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from careerops.domain.dashboard import (
    ActionItemStatusCounts,
    DashboardCounts,
    DashboardFocusItems,
    DashboardSummary,
    JobStatusCounts,
)
from careerops.services.dashboard import (
    DASHBOARD_FOCUS_LIMIT,
    DashboardFocusService,
    DashboardService,
)


def make_counts() -> DashboardCounts:
    return DashboardCounts(
        jobs=JobStatusCounts(
            total=3,
            saved=1,
            preparing=1,
            applied=1,
            interview=0,
            offer=0,
            rejected=0,
            withdrawn=0,
        ),
        action_items=ActionItemStatusCounts(total=4, todo=2, doing=1, done=1),
    )


class CountingSummaryReader:
    def __init__(self, counts: DashboardCounts) -> None:
        self.counts = counts
        self.calls = 0

    async def get_counts(self, user_id: UUID) -> DashboardCounts:
        self.calls += 1
        return self.counts


class InMemoryDashboardCache:
    def __init__(self, cached: DashboardSummary | None = None) -> None:
        self.cached = cached
        self.set_calls: list[tuple[UUID, DashboardSummary]] = []
        self.invalidated_user_ids: list[UUID] = []

    async def get(self, user_id: UUID) -> DashboardSummary | None:
        return self.cached

    async def set(self, user_id: UUID, summary: DashboardSummary) -> None:
        self.cached = summary
        self.set_calls.append((user_id, summary))

    async def invalidate(self, user_id: UUID) -> None:
        self.invalidated_user_ids.append(user_id)


@pytest.mark.asyncio
async def test_cache_miss_reads_postgres_shape_and_caches_generated_snapshot() -> None:
    user_id = uuid4()
    generated_at = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    reader = CountingSummaryReader(make_counts())
    cache = InMemoryDashboardCache()

    summary = await DashboardService(
        reader,
        cache,
        clock=lambda: generated_at,
    ).get_summary(user_id)

    assert summary == DashboardSummary(
        generated_at=generated_at,
        jobs=reader.counts.jobs,
        action_items=reader.counts.action_items,
    )
    assert reader.calls == 1
    assert cache.set_calls == [(user_id, summary)]


@pytest.mark.asyncio
async def test_cache_hit_skips_postgres_and_preserves_generated_at() -> None:
    user_id = uuid4()
    cached = DashboardSummary(
        generated_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        jobs=make_counts().jobs,
        action_items=make_counts().action_items,
    )
    reader = CountingSummaryReader(make_counts())
    cache = InMemoryDashboardCache(cached)

    summary = await DashboardService(reader, cache).get_summary(user_id)

    assert summary is cached
    assert reader.calls == 0
    assert cache.set_calls == []


class RecordingFocusReader:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, date, int]] = []

    async def get_focus_items(self, user_id: UUID, today: date, limit: int) -> DashboardFocusItems:
        self.calls.append((user_id, today, limit))
        return DashboardFocusItems(upcoming_deadlines=(), recent_jobs=(), open_action_items=())


@pytest.mark.asyncio
async def test_focus_uses_utc_date_and_bounded_limit() -> None:
    user_id = uuid4()
    # 23:30 at UTC-5 is already the next calendar day in UTC.
    local_evening = datetime(2026, 10, 28, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    reader = RecordingFocusReader()

    focus = await DashboardFocusService(reader, clock=lambda: local_evening).get_focus(user_id)

    assert focus.today == date(2026, 10, 29)
    assert focus.generated_at == local_evening
    assert reader.calls == [(user_id, date(2026, 10, 29), DASHBOARD_FOCUS_LIMIT)]
