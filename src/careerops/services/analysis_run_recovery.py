from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import AnalysisRunDispatchError
from careerops.services.analysis_runs import AnalysisRunDispatcher


class AnalysisRunRecoveryStore(Protocol):
    async def requeue_stale_analysis_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[UUID]: ...

    async def list_queued_analysis_run_ids(self, limit: int) -> list[UUID]: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class AnalysisRunRecoveryResult:
    requeued: int
    dispatched: int
    dispatch_failed: int


class AnalysisRunRecoveryService:
    def __init__(
        self,
        store: AnalysisRunRecoveryStore,
        dispatcher: AnalysisRunDispatcher,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher

    async def recover(self, stale_before: datetime, limit: int) -> AnalysisRunRecoveryResult:
        requeued_ids = await self._store.requeue_stale_analysis_runs(stale_before, limit)
        if requeued_ids:
            await self._store.commit()

        queued_ids = await self._store.list_queued_analysis_run_ids(limit)
        dispatched = 0
        dispatch_failed = 0
        for analysis_run_id in queued_ids:
            try:
                await self._dispatcher.dispatch(analysis_run_id)
                dispatched += 1
            except AnalysisRunDispatchError:
                dispatch_failed += 1
        return AnalysisRunRecoveryResult(
            requeued=len(requeued_ids),
            dispatched=dispatched,
            dispatch_failed=dispatch_failed,
        )
