from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.dashboard import (
    DashboardCounts,
    DashboardFocus,
    DashboardFocusItems,
    DashboardSummary,
)


class DashboardSummaryReader(Protocol):
    async def get_counts(self, user_id: UUID) -> DashboardCounts: ...


class DashboardCacheInvalidator(Protocol):
    async def invalidate(self, user_id: UUID) -> None: ...


class DashboardCache(DashboardCacheInvalidator, Protocol):
    async def get(self, user_id: UUID) -> DashboardSummary | None: ...

    async def set(self, user_id: UUID, summary: DashboardSummary) -> None: ...


class DashboardService:
    def __init__(
        self,
        summaries: DashboardSummaryReader,
        cache: DashboardCache,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._summaries = summaries
        self._cache = cache
        self._clock = clock or utc_now

    async def get_summary(self, user_id: UUID) -> DashboardSummary:
        cached = await self._cache.get(user_id)
        if cached is not None:
            return cached

        counts = await self._summaries.get_counts(user_id)
        summary = DashboardSummary(
            generated_at=self._clock(),
            jobs=counts.jobs,
            action_items=counts.action_items,
        )
        await self._cache.set(user_id, summary)
        return summary


DASHBOARD_FOCUS_LIMIT = 5


class DashboardFocusReader(Protocol):
    async def get_focus_items(
        self, user_id: UUID, today: date, limit: int
    ) -> DashboardFocusItems: ...


# Deliberately uncached: it reads a few indexed rows, so it adds no Redis invalidation paths.
class DashboardFocusService:
    def __init__(
        self,
        focus: DashboardFocusReader,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._focus = focus
        self._clock = clock or utc_now

    async def get_focus(self, user_id: UUID) -> DashboardFocus:
        now = self._clock()
        today = now.astimezone(UTC).date()
        items = await self._focus.get_focus_items(user_id, today, DASHBOARD_FOCUS_LIMIT)
        return DashboardFocus(generated_at=now, today=today, items=items)


def utc_now() -> datetime:
    return datetime.now(UTC)
