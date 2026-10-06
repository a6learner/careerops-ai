import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from careerops.adapters.redis_analysis_rate_limiter import (
    RedisAnalysisRateLimiter,
    analysis_rate_limit_key,
)
from careerops.core.config import Settings
from careerops.domain.analysis_runs import AnalysisRateLimitReservation
from careerops.domain.errors import AnalysisRateLimitExceededError

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("CAREEROPS_RUN_INTEGRATION") != "1",
    reason="requires local Redis container",
)
@pytest.mark.asyncio
async def test_analysis_rate_limit_is_atomic_and_user_scoped() -> None:
    client = Redis.from_url(Settings().redis_url, decode_responses=True)
    first_user = uuid4()
    second_user = uuid4()
    limiter = RedisAnalysisRateLimiter(client, limit=2, window_seconds=60)
    try:
        outcomes = await asyncio.gather(
            limiter.reserve(first_user),
            limiter.reserve(first_user),
            limiter.reserve(first_user),
            return_exceptions=True,
        )
        reservations = [
            outcome for outcome in outcomes if isinstance(outcome, AnalysisRateLimitReservation)
        ]
        rejections = [
            outcome for outcome in outcomes if isinstance(outcome, AnalysisRateLimitExceededError)
        ]

        assert len(reservations) == 2
        assert len(rejections) == 1
        assert 1 <= rejections[0].retry_after_seconds <= 60
        assert isinstance(await limiter.reserve(second_user), AnalysisRateLimitReservation)
    finally:
        await client.delete(
            analysis_rate_limit_key(first_user),
            analysis_rate_limit_key(second_user),
        )
        await client.aclose()
