from collections.abc import Callable
from typing import cast

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AsyncIO

from careerops.core.config import get_settings

# Dramatiq does not publish constructor types for RedisBroker.
redis_broker_factory = cast(Callable[..., RedisBroker], RedisBroker)
redis_broker = redis_broker_factory(url=get_settings().redis_url, namespace="careerops")
redis_broker.add_middleware(AsyncIO())
dramatiq.set_broker(redis_broker)
