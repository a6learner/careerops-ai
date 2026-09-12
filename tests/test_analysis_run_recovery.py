from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import AnalysisRunDispatchError
from careerops.services.analysis_run_recovery import AnalysisRunRecoveryService


class RecoveryStore:
    def __init__(self, requeued: list[UUID], queued: list[UUID]) -> None:
        self.requeued = requeued
        self.queued = queued
        self.committed = False

    async def requeue_stale_analysis_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[UUID]:
        return self.requeued[:limit]

    async def list_queued_analysis_run_ids(self, limit: int) -> list[UUID]:
        return self.queued[:limit]

    async def commit(self) -> None:
        self.committed = True


class Dispatcher:
    def __init__(self, failing_id: UUID) -> None:
        self.failing_id = failing_id
        self.dispatched: list[UUID] = []

    async def dispatch(self, analysis_run_id: UUID) -> None:
        if analysis_run_id == self.failing_id:
            raise AnalysisRunDispatchError()
        self.dispatched.append(analysis_run_id)


@pytest.mark.asyncio
async def test_recovery_requeues_stale_runs_and_reports_dispatch_failures() -> None:
    requeued_id = uuid4()
    queued_id = uuid4()
    failing_id = uuid4()
    store = RecoveryStore([requeued_id], [requeued_id, queued_id, failing_id])
    dispatcher = Dispatcher(failing_id)

    result = await AnalysisRunRecoveryService(store, dispatcher).recover(datetime.now(UTC), 10)

    assert result.requeued == 1
    assert result.dispatched == 2
    assert result.dispatch_failed == 1
    assert store.committed
    assert dispatcher.dispatched == [requeued_id, queued_id]
