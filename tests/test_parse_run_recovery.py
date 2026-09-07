from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from careerops.domain.errors import ParseRunDispatchError
from careerops.services.parse_run_recovery import ParseRunRecoveryResult, ParseRunRecoveryService
from careerops.workers import recovery


class InMemoryRecoveryStore:
    def __init__(self, requeued: list[UUID], queued: list[UUID]) -> None:
        self.requeued = requeued
        self.queued = queued
        self.committed = False

    async def requeue_stale_parse_runs(self, stale_before: datetime, limit: int) -> list[UUID]:
        return self.requeued[:limit]

    async def list_queued_parse_run_ids(self, limit: int) -> list[UUID]:
        return self.queued[:limit]

    async def commit(self) -> None:
        self.committed = True


class SelectiveDispatcher:
    def __init__(self, failing_id: UUID) -> None:
        self.failing_id = failing_id
        self.dispatched: list[UUID] = []

    async def dispatch(self, parse_run_id: UUID) -> None:
        if parse_run_id == self.failing_id:
            raise ParseRunDispatchError()
        self.dispatched.append(parse_run_id)


@pytest.mark.asyncio
async def test_recovery_requeues_stale_runs_and_reports_dispatch_failures() -> None:
    requeued_id = uuid4()
    queued_id = uuid4()
    failing_id = uuid4()
    store = InMemoryRecoveryStore([requeued_id], [requeued_id, queued_id, failing_id])
    dispatcher = SelectiveDispatcher(failing_id)

    result = await ParseRunRecoveryService(store, dispatcher).recover(datetime.now(UTC), 10)

    assert result.requeued == 1
    assert result.dispatched == 2
    assert result.dispatch_failed == 1
    assert store.committed
    assert dispatcher.dispatched == [requeued_id, queued_id]


def test_recovery_command_exits_nonzero_when_dispatch_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def recover_with_failure() -> ParseRunRecoveryResult:
        return ParseRunRecoveryResult(requeued=1, dispatched=2, dispatch_failed=1)

    monkeypatch.setattr(recovery, "recover_parse_runs", recover_with_failure)

    with pytest.raises(SystemExit) as raised:
        recovery.main()

    assert raised.value.code == 1
    assert capsys.readouterr().out == "requeued=1 dispatched=2 dispatch_failed=1\n"
