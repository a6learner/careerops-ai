import logging
from typing import cast
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from careerops.domain.analysis_runs import AnalysisRateLimitReservation
from careerops.domain.errors import (
    AnalysisRateLimitExceededError,
    AnalysisRateLimitUnavailableError,
)

logger = logging.getLogger(__name__)

_RESERVE_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local member = ARGV[3]
local redis_time = redis.call('TIME')
local now_ms = (tonumber(redis_time[1]) * 1000) + math.floor(tonumber(redis_time[2]) / 1000)
local cutoff_ms = now_ms - window_ms

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = math.max(1, math.ceil((tonumber(oldest[2]) + window_ms - now_ms) / 1000))
    redis.call('PEXPIRE', key, window_ms)
    return {0, retry_after}
end

redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
return {1, 0}
"""


class RedisAnalysisRateLimiter:
    def __init__(self, client: Redis, *, limit: int, window_seconds: int) -> None:
        self._client = client
        self._limit = limit
        self._window_seconds = window_seconds

    async def reserve(self, user_id: UUID) -> AnalysisRateLimitReservation:
        reservation = AnalysisRateLimitReservation(token=str(uuid4()))
        try:
            raw_result = await self._client.eval(
                _RESERVE_SCRIPT,
                1,
                analysis_rate_limit_key(user_id),
                self._limit,
                self._window_seconds * 1_000,
                reservation.token,
            )
        except RedisError as exc:
            raise AnalysisRateLimitUnavailableError() from exc

        # redis-py exposes Lua return values as Any, so validate at this adapter boundary.
        if not isinstance(raw_result, list):
            raise AnalysisRateLimitUnavailableError()
        result = cast(list[object], raw_result)
        if (
            len(result) != 2
            or not isinstance(result[0], int)
            or isinstance(result[0], bool)
            or not isinstance(result[1], int)
            or isinstance(result[1], bool)
        ):
            raise AnalysisRateLimitUnavailableError()
        if result[0] == 0:
            raise AnalysisRateLimitExceededError(retry_after_seconds=max(1, result[1]))
        if result[0] != 1 or result[1] != 0:
            raise AnalysisRateLimitUnavailableError()
        return reservation

    async def release(
        self,
        user_id: UUID,
        reservation: AnalysisRateLimitReservation,
    ) -> None:
        try:
            await self._client.zrem(analysis_rate_limit_key(user_id), reservation.token)
        except RedisError as exc:
            logger.warning(
                "analysis_rate_limit_release_failed",
                extra={
                    "user_id": str(user_id),
                    "error_type": type(exc).__name__,
                },
            )


def analysis_rate_limit_key(user_id: UUID) -> str:
    return f"careerops:rate-limit:analysis:v1:user:{user_id}"
