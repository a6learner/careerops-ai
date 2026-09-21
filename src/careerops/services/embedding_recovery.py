from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import EmbeddingRunDispatchError


class EmbeddingRunDispatcher(Protocol):
    async def dispatch(self, run_id: UUID) -> None: ...


class EmbeddingRecoveryStore(Protocol):
    async def reconcile_missing_runs(
        self,
        model_name: str,
        input_version: str,
        limit: int,
    ) -> list[UUID]: ...

    async def requeue_stale_runs(self, stale_before: datetime, limit: int) -> list[UUID]: ...

    async def list_queued_run_ids(self, limit: int) -> list[UUID]: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class EmbeddingRecoveryResult:
    reconciled: int
    requeued: int
    dispatched: int
    dispatch_failed: int


class EmbeddingRecoveryService:
    def __init__(
        self,
        store: EmbeddingRecoveryStore,
        dispatcher: EmbeddingRunDispatcher,
        model_name: str,
        input_version: str,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._model_name = model_name
        self._input_version = input_version

    async def recover(self, stale_before: datetime, limit: int) -> EmbeddingRecoveryResult:
        reconciled_ids = await self._store.reconcile_missing_runs(
            self._model_name,
            self._input_version,
            limit,
        )
        requeued_ids = await self._store.requeue_stale_runs(stale_before, limit)
        if reconciled_ids or requeued_ids:
            await self._store.commit()

        queued_ids = await self._store.list_queued_run_ids(limit)
        dispatched = 0
        dispatch_failed = 0
        for run_id in queued_ids:
            try:
                await self._dispatcher.dispatch(run_id)
                dispatched += 1
            except EmbeddingRunDispatchError:
                dispatch_failed += 1
        return EmbeddingRecoveryResult(
            reconciled=len(reconciled_ids),
            requeued=len(requeued_ids),
            dispatched=dispatched,
            dispatch_failed=dispatch_failed,
        )
