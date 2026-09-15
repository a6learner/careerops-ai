import json
import logging
from datetime import datetime
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from careerops.domain.dashboard import (
    ActionItemStatusCounts,
    DashboardSummary,
    JobStatusCounts,
)

logger = logging.getLogger(__name__)


class RedisDashboardCache:
    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    async def get(self, user_id: UUID) -> DashboardSummary | None:
        try:
            value = await self._client.get(cache_key(user_id))
        except RedisError as exc:
            logger.warning(
                "Dashboard cache read failed user_id=%s error_type=%s",
                user_id,
                type(exc).__name__,
            )
            return None
        if value is None:
            return None

        try:
            return deserialize_summary(value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Dashboard cache value is invalid user_id=%s error_type=%s",
                user_id,
                type(exc).__name__,
            )
            await self.invalidate(user_id)
            return None

    async def set(self, user_id: UUID, summary: DashboardSummary) -> None:
        try:
            await self._client.set(
                cache_key(user_id),
                serialize_summary(summary),
                ex=self._ttl_seconds,
            )
        except RedisError as exc:
            logger.warning(
                "Dashboard cache write failed user_id=%s error_type=%s",
                user_id,
                type(exc).__name__,
            )

    async def invalidate(self, user_id: UUID) -> None:
        try:
            await self._client.delete(cache_key(user_id))
        except RedisError as exc:
            logger.warning(
                "Dashboard cache invalidation failed user_id=%s error_type=%s",
                user_id,
                type(exc).__name__,
            )


def cache_key(user_id: UUID) -> str:
    return f"careerops:cache:dashboard-summary:v1:user:{user_id}"


def serialize_summary(summary: DashboardSummary) -> str:
    return json.dumps(
        {
            "generated_at": summary.generated_at.isoformat(),
            "jobs": {
                "total": summary.jobs.total,
                "saved": summary.jobs.saved,
                "preparing": summary.jobs.preparing,
                "applied": summary.jobs.applied,
                "interview": summary.jobs.interview,
                "offer": summary.jobs.offer,
                "rejected": summary.jobs.rejected,
                "withdrawn": summary.jobs.withdrawn,
            },
            "action_items": {
                "total": summary.action_items.total,
                "todo": summary.action_items.todo,
                "doing": summary.action_items.doing,
                "done": summary.action_items.done,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def deserialize_summary(value: str | bytes) -> DashboardSummary:
    raw = value.decode("utf-8") if isinstance(value, bytes) else value
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Dashboard cache payload must be an object.")
    jobs = require_mapping(payload, "jobs")
    action_items = require_mapping(payload, "action_items")
    return DashboardSummary(
        generated_at=datetime.fromisoformat(require_string(payload, "generated_at")),
        jobs=JobStatusCounts(
            total=require_count(jobs, "total"),
            saved=require_count(jobs, "saved"),
            preparing=require_count(jobs, "preparing"),
            applied=require_count(jobs, "applied"),
            interview=require_count(jobs, "interview"),
            offer=require_count(jobs, "offer"),
            rejected=require_count(jobs, "rejected"),
            withdrawn=require_count(jobs, "withdrawn"),
        ),
        action_items=ActionItemStatusCounts(
            total=require_count(action_items, "total"),
            todo=require_count(action_items, "todo"),
            doing=require_count(action_items, "doing"),
            done=require_count(action_items, "done"),
        ),
    )


def require_mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be an object.")
    return cast(dict[str, object], value)


def require_string(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string.")
    return value


def require_count(payload: dict[str, object], key: str) -> int:
    value = payload[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TypeError(f"{key} must be a non-negative integer.")
    return value
