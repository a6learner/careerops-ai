from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.dashboard import DashboardCounts, DashboardSummary


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


def utc_now() -> datetime:
    return datetime.now(UTC)
