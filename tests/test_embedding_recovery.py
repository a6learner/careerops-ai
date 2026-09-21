from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import EmbeddingRunDispatchError
from careerops.services.embedding_recovery import EmbeddingRecoveryService


class RecoveryStore:
    def __init__(self, reconciled: list[UUID], requeued: list[UUID], queued: list[UUID]) -> None:
        self.reconciled = reconciled
        self.requeued = requeued
        self.queued = queued
        self.committed = False

    async def reconcile_missing_runs(
        self,
        model_name: str,
        input_version: str,
        limit: int,
    ) -> list[UUID]:
        return self.reconciled[:limit]

    async def requeue_stale_runs(self, stale_before: datetime, limit: int) -> list[UUID]:
        return self.requeued[:limit]

    async def list_queued_run_ids(self, limit: int) -> list[UUID]:
        return self.queued[:limit]

    async def commit(self) -> None:
        self.committed = True


class Dispatcher:
    def __init__(self, failing_id: UUID) -> None:
        self.failing_id = failing_id
        self.dispatched: list[UUID] = []

    async def dispatch(self, run_id: UUID) -> None:
        if run_id == self.failing_id:
            raise EmbeddingRunDispatchError()
        self.dispatched.append(run_id)


@pytest.mark.asyncio
async def test_recovery_reconciles_requeues_and_reports_dispatch_failures() -> None:
    reconciled_id = uuid4()
    requeued_id = uuid4()
    failing_id = uuid4()
    store = RecoveryStore(
        [reconciled_id],
        [requeued_id],
        [reconciled_id, requeued_id, failing_id],
    )
    dispatcher = Dispatcher(failing_id)
    service = EmbeddingRecoveryService(store, dispatcher, "model", "input-v1")

    result = await service.recover(datetime.now(UTC), 10)

    assert result.reconciled == 1
    assert result.requeued == 1
    assert result.dispatched == 2
    assert result.dispatch_failed == 1
    assert store.committed
    assert dispatcher.dispatched == [reconciled_id, requeued_id]
