from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError

from careerops.domain.errors import ParseRunDispatchError
from careerops.workers.dispatcher import DramatiqParseRunDispatcher


class RecordingActor:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    def send(self, parse_run_id: str) -> object:
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.sent.append(parse_run_id)
        return object()


@pytest.mark.asyncio
async def test_dispatcher_sends_only_the_parse_run_id() -> None:
    actor = RecordingActor()
    parse_run_id = uuid4()

    await DramatiqParseRunDispatcher(actor).dispatch(parse_run_id)

    assert actor.sent == [str(parse_run_id)]


@pytest.mark.asyncio
async def test_dispatcher_converts_redis_failure_to_domain_error() -> None:
    with pytest.raises(ParseRunDispatchError):
        await DramatiqParseRunDispatcher(RecordingActor(fail=True)).dispatch(uuid4())
