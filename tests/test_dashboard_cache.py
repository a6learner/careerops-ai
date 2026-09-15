from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from careerops.cache.dashboard import (
    RedisDashboardCache,
    cache_key,
    deserialize_summary,
    serialize_summary,
)
from careerops.domain.dashboard import (
    ActionItemStatusCounts,
    DashboardSummary,
    JobStatusCounts,
)


def make_summary() -> DashboardSummary:
    return DashboardSummary(
        generated_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        jobs=JobStatusCounts(
            total=2,
            saved=1,
            preparing=0,
            applied=1,
            interview=0,
            offer=0,
            rejected=0,
            withdrawn=0,
        ),
        action_items=ActionItemStatusCounts(total=3, todo=1, doing=1, done=1),
    )


class FakeRedis:
    def __init__(self, value: str | None = None, *, fail: bool = False) -> None:
        self.value = value
        self.fail = fail
        self.set_arguments: tuple[str, str, int] | None = None
        self.deleted_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise RedisError("unavailable")
        return self.value

    async def set(self, key: str, value: str, *, ex: int) -> None:
        if self.fail:
            raise RedisError("unavailable")
        self.value = value
        self.set_arguments = (key, value, ex)

    async def delete(self, key: str) -> None:
        if self.fail:
            raise RedisError("unavailable")
        self.value = None
        self.deleted_keys.append(key)


def cache_for(fake: FakeRedis, ttl_seconds: int = 30) -> RedisDashboardCache:
    return RedisDashboardCache(cast(Redis, fake), ttl_seconds)


def test_dashboard_cache_json_round_trips() -> None:
    summary = make_summary()

    assert deserialize_summary(serialize_summary(summary)) == summary


@pytest.mark.asyncio
async def test_dashboard_cache_uses_user_scoped_versioned_key_and_ttl() -> None:
    user_id = uuid4()
    fake = FakeRedis()
    cache = cache_for(fake)

    await cache.set(user_id, make_summary())

    assert fake.set_arguments is not None
    assert fake.set_arguments[0] == cache_key(user_id)
    assert fake.set_arguments[2] == 30
    assert await cache.get(user_id) == make_summary()


@pytest.mark.asyncio
async def test_invalid_cache_value_becomes_miss_and_is_deleted() -> None:
    user_id = uuid4()
    fake = FakeRedis("not-json")

    assert await cache_for(fake).get(user_id) is None
    assert fake.deleted_keys == [cache_key(user_id)]


@pytest.mark.asyncio
async def test_redis_failures_are_fail_open() -> None:
    user_id = uuid4()
    cache = cache_for(FakeRedis(fail=True))

    assert await cache.get(user_id) is None
    await cache.set(user_id, make_summary())
    await cache.invalidate(user_id)
