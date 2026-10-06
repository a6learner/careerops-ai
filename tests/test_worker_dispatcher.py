from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError

from careerops.domain.analysis_runs import AnalysisDispatchSource
from careerops.domain.errors import (
    AnalysisRunDispatchError,
    EmbeddingRunDispatchError,
    ParseRunDispatchError,
)
from careerops.workers.dispatcher import (
    DramatiqAnalysisRunDispatcher,
    DramatiqEmbeddingRunDispatcher,
    DramatiqParseRunDispatcher,
)


class RecordingActor:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, ...]] = []

    def send(self, *args: str) -> object:
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.sent.append(args)
        return object()


@pytest.mark.asyncio
async def test_dispatcher_sends_only_the_parse_run_id() -> None:
    actor = RecordingActor()
    parse_run_id = uuid4()

    await DramatiqParseRunDispatcher(actor).dispatch(parse_run_id)

    assert actor.sent == [(str(parse_run_id),)]


@pytest.mark.asyncio
async def test_dispatcher_converts_redis_failure_to_domain_error() -> None:
    with pytest.raises(ParseRunDispatchError):
        await DramatiqParseRunDispatcher(RecordingActor(fail=True)).dispatch(uuid4())


@pytest.mark.asyncio
async def test_analysis_dispatcher_sends_correlation_context() -> None:
    actor = RecordingActor()
    analysis_run_id = uuid4()

    await DramatiqAnalysisRunDispatcher(actor).dispatch(
        analysis_run_id,
        "request-1",
        AnalysisDispatchSource.SUBMISSION,
    )

    assert actor.sent == [
        (str(analysis_run_id), "request-1", AnalysisDispatchSource.SUBMISSION.value)
    ]


@pytest.mark.asyncio
async def test_analysis_dispatcher_converts_redis_failure_to_domain_error() -> None:
    with pytest.raises(AnalysisRunDispatchError):
        await DramatiqAnalysisRunDispatcher(RecordingActor(fail=True)).dispatch(
            uuid4(),
            "request-1",
            AnalysisDispatchSource.SUBMISSION,
        )


@pytest.mark.asyncio
async def test_embedding_dispatcher_sends_only_the_run_id() -> None:
    actor = RecordingActor()
    run_id = uuid4()

    await DramatiqEmbeddingRunDispatcher(actor).dispatch(run_id)

    assert actor.sent == [(str(run_id),)]


@pytest.mark.asyncio
async def test_embedding_dispatcher_converts_redis_failure_to_domain_error() -> None:
    with pytest.raises(EmbeddingRunDispatchError):
        await DramatiqEmbeddingRunDispatcher(RecordingActor(fail=True)).dispatch(uuid4())
