from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops.domain.errors import ParseRunDispatchError
from careerops.services.parse_runs import ParseRunDispatcher


class ParseRunRecoveryStore(Protocol):
    async def requeue_stale_parse_runs(
        self,
        stale_before: datetime,
        limit: int,
    ) -> list[UUID]: ...

    async def list_queued_parse_run_ids(self, limit: int) -> list[UUID]: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True)
class ParseRunRecoveryResult:
    requeued: int
    dispatched: int
    dispatch_failed: int


class ParseRunRecoveryService:
    def __init__(
        self,
        store: ParseRunRecoveryStore,
        dispatcher: ParseRunDispatcher,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher

    async def recover(self, stale_before: datetime, limit: int) -> ParseRunRecoveryResult:
        requeued_ids = await self._store.requeue_stale_parse_runs(stale_before, limit)
        if requeued_ids:
            await self._store.commit()

        queued_ids = await self._store.list_queued_parse_run_ids(limit)
        dispatched = 0
        dispatch_failed = 0
        for parse_run_id in queued_ids:
            try:
                await self._dispatcher.dispatch(parse_run_id)
                dispatched += 1
            except ParseRunDispatchError:
                dispatch_failed += 1
        return ParseRunRecoveryResult(
            requeued=len(requeued_ids),
            dispatched=dispatched,
            dispatch_failed=dispatch_failed,
        )
