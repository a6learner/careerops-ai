from unittest.mock import AsyncMock

import pytest

from careerops.cache.health import RedisReadinessChecker


@pytest.mark.asyncio
async def test_redis_readiness_reports_ping_result() -> None:
    client = AsyncMock()
    client.ping.return_value = True

    assert await RedisReadinessChecker(client).is_ready()


@pytest.mark.asyncio
async def test_redis_readiness_converts_connection_failure_to_not_ready() -> None:
    client = AsyncMock()
    client.ping.side_effect = ConnectionError("redis unavailable")

    assert not await RedisReadinessChecker(client).is_ready()
