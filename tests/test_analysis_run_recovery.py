import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.analysis_runs import AnalysisDispatchSource, AnalysisRunRecoveryItem
from careerops.domain.errors import AnalysisRunDispatchError
from careerops.services.analysis_run_recovery import AnalysisRunRecoveryService


class RecoveryStore:
    def __init__(self, requeued: list[AnalysisRunRecoveryItem], queued: list[UUID]) -> None:
        self.requeued = requeued
        self.queued = queued
        self.committed = False

    async def requeue_stale_analysis_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[AnalysisRunRecoveryItem]:
        return self.requeued[:limit]

    async def list_queued_analysis_run_ids(self, limit: int) -> list[UUID]:
        return self.queued[:limit]

    async def commit(self) -> None:
        self.committed = True


class Dispatcher:
    def __init__(self, failing_id: UUID) -> None:
        self.failing_id = failing_id
        self.dispatched: list[UUID] = []
        self.correlations: list[tuple[str, AnalysisDispatchSource]] = []

    async def dispatch(
        self,
        analysis_run_id: UUID,
        request_id: str,
        dispatch_source: AnalysisDispatchSource,
    ) -> None:
        if analysis_run_id == self.failing_id:
            raise AnalysisRunDispatchError()
        self.dispatched.append(analysis_run_id)
        self.correlations.append((request_id, dispatch_source))


@pytest.mark.asyncio
async def test_recovery_requeues_stale_runs_and_reports_dispatch_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    requeued_id = uuid4()
    queued_id = uuid4()
    failing_id = uuid4()
    store = RecoveryStore(
        [AnalysisRunRecoveryItem(id=requeued_id, attempt=2)],
        [requeued_id, queued_id, failing_id],
    )
    dispatcher = Dispatcher(failing_id)

    with caplog.at_level(logging.INFO):
        result = await AnalysisRunRecoveryService(store, dispatcher).recover(
            datetime.now(UTC),
            10,
            "recovery-1",
        )

    assert result.requeued == 1
    assert result.dispatched == 2
    assert result.dispatch_failed == 1
    assert store.committed
    assert dispatcher.dispatched == [requeued_id, queued_id]
    assert dispatcher.correlations == [
        ("recovery-1", AnalysisDispatchSource.RECOVERY),
        ("recovery-1", AnalysisDispatchSource.RECOVERY),
    ]
    requeued = next(
        record for record in caplog.records if record.getMessage() == "analysis_run_requeued"
    )
    assert requeued.request_id == "recovery-1"
    assert requeued.run_id == str(requeued_id)
    assert requeued.attempt == 2
