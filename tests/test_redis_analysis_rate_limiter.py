from typing import cast
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from careerops.adapters.redis_analysis_rate_limiter import (
    RedisAnalysisRateLimiter,
    analysis_rate_limit_key,
)
from careerops.domain.errors import (
    AnalysisRateLimitExceededError,
    AnalysisRateLimitUnavailableError,
)


class FakeRedis:
    def __init__(
        self,
        result: list[int] | None = None,
        *,
        fail_eval: bool = False,
        fail_release: bool = False,
    ) -> None:
        self.result: object = result if result is not None else [1, 0]
        self.fail_eval = fail_eval
        self.fail_release = fail_release
        self.eval_arguments: tuple[object, ...] | None = None
        self.removed: tuple[str, str] | None = None

    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        if self.fail_eval:
            raise RedisError("unavailable")
        self.eval_arguments = (script, numkeys, *keys_and_args)
        return self.result

    async def zrem(self, key: str, member: str) -> int:
        if self.fail_release:
            raise RedisError("unavailable")
        self.removed = (key, member)
        return 1


def limiter_for(fake: FakeRedis) -> RedisAnalysisRateLimiter:
    return RedisAnalysisRateLimiter(cast(Redis, fake), limit=5, window_seconds=3_600)


@pytest.mark.asyncio
async def test_reserve_uses_user_scoped_key_and_configured_window() -> None:
    user_id = uuid4()
    fake = FakeRedis()

    reservation = await limiter_for(fake).reserve(user_id)

    assert fake.eval_arguments is not None
    assert fake.eval_arguments[1:5] == (
        1,
        analysis_rate_limit_key(user_id),
        5,
        3_600_000,
    )
    assert fake.eval_arguments[5] == reservation.token


@pytest.mark.asyncio
async def test_limit_rejection_preserves_retry_after() -> None:
    with pytest.raises(AnalysisRateLimitExceededError) as captured:
        await limiter_for(FakeRedis([0, 43])).reserve(uuid4())

    assert captured.value.retry_after_seconds == 43


@pytest.mark.asyncio
async def test_reserve_redis_failure_fails_closed() -> None:
    with pytest.raises(AnalysisRateLimitUnavailableError):
        await limiter_for(FakeRedis(fail_eval=True)).reserve(uuid4())


@pytest.mark.asyncio
async def test_invalid_lua_result_fails_closed() -> None:
    fake = FakeRedis()
    fake.result = "invalid"

    with pytest.raises(AnalysisRateLimitUnavailableError):
        await limiter_for(fake).reserve(uuid4())


@pytest.mark.asyncio
async def test_release_removes_only_the_reservation_and_is_best_effort() -> None:
    user_id = uuid4()
    fake = FakeRedis()
    limiter = limiter_for(fake)
    reservation = await limiter.reserve(user_id)

    await limiter.release(user_id, reservation)
    await limiter_for(FakeRedis(fail_release=True)).release(user_id, reservation)

    assert fake.removed == (analysis_rate_limit_key(user_id), reservation.token)
