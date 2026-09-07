import os
from uuid import uuid4

import dramatiq
import pytest
from dramatiq.brokers.redis import RedisBroker

from careerops.core.config import get_settings
from careerops.workers.dispatcher import DramatiqParseRunDispatcher

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local Redis container",
)
@pytest.mark.asyncio
async def test_dispatcher_enqueues_parse_run_id_in_redis() -> None:
    namespace = f"careerops-test-{uuid4()}"
    queue_name = "parse-runs-test"
    broker = RedisBroker(url=get_settings().redis_url, namespace=namespace)

    def do_nothing(parse_run_id: str) -> None:
        return None

    actor = dramatiq.actor(
        do_nothing,
        actor_name=f"test_parse_run_{uuid4()}",
        broker=broker,
        queue_name=queue_name,
    )
    parse_run_id = uuid4()
    consumer = broker.consume(queue_name, timeout=1_000)
    connected = False
    try:
        await DramatiqParseRunDispatcher(actor).dispatch(parse_run_id)
        connected = True
        message = next(consumer)

        assert message is not None
        assert message.args == (str(parse_run_id),)
        consumer.ack(message)
    finally:
        consumer.close()
        if connected:
            broker.flush_all()
        broker.close()
