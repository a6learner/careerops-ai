import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.analysis_runs import AnalysisDispatchSource, AnalysisRunRecoveryItem
from careerops.domain.errors import AnalysisRunDispatchError
from careerops.services.analysis_runs import AnalysisRunDispatcher

logger = logging.getLogger(__name__)


class AnalysisRunRecoveryStore(Protocol):
    async def requeue_stale_analysis_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[AnalysisRunRecoveryItem]: ...

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

    async def recover(
        self,
        stale_before: datetime,
        limit: int,
        request_id: str,
    ) -> AnalysisRunRecoveryResult:
        requeued_items = await self._store.requeue_stale_analysis_runs(stale_before, limit)
        if requeued_items:
            await self._store.commit()
            for item in requeued_items:
                logger.info(
                    "analysis_run_requeued",
                    extra={
                        "request_id": request_id,
                        "run_type": "analysis",
                        "run_id": str(item.id),
                        "attempt": item.attempt,
                        "dispatch_source": AnalysisDispatchSource.RECOVERY.value,
                        "status": "queued",
                    },
                )

        queued_ids = await self._store.list_queued_analysis_run_ids(limit)
        dispatched = 0
        dispatch_failed = 0
        for analysis_run_id in queued_ids:
            try:
                await self._dispatcher.dispatch(
                    analysis_run_id,
                    request_id,
                    AnalysisDispatchSource.RECOVERY,
                )
                dispatched += 1
            except AnalysisRunDispatchError:
                dispatch_failed += 1
        result = AnalysisRunRecoveryResult(
            requeued=len(requeued_items),
            dispatched=dispatched,
            dispatch_failed=dispatch_failed,
        )
        logger.info(
            "analysis_recovery_completed",
            extra={
                "request_id": request_id,
                "run_type": "analysis",
                "dispatch_source": AnalysisDispatchSource.RECOVERY.value,
                "requeued": result.requeued,
                "dispatched": result.dispatched,
                "dispatch_failed": result.dispatch_failed,
            },
        )
        return result
