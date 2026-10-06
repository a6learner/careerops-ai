from uuid import UUID, uuid4

import pytest

from careerops.domain.analysis_runs import AnalysisDispatchSource
from careerops.workers import tasks


@pytest.mark.asyncio
async def test_legacy_analysis_message_gets_safe_local_correlation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_run_id = uuid4()
    observed: list[tuple[UUID, str | None, AnalysisDispatchSource]] = []

    async def record_execution(
        run_id: UUID,
        matcher: object | None = None,
        *,
        request_id: str | None = None,
        dispatch_source: AnalysisDispatchSource = AnalysisDispatchSource.LEGACY,
    ) -> bool:
        observed.append((run_id, request_id, dispatch_source))
        return True

    monkeypatch.setattr(tasks, "execute_analysis_run_async", record_execution)

    await tasks.execute_analysis_run.fn.__wrapped__(str(analysis_run_id))

    assert observed[0][0] == analysis_run_id
    assert observed[0][1] is not None
    UUID(observed[0][1] or "")
    assert observed[0][2] is AnalysisDispatchSource.LEGACY
