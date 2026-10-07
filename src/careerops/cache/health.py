from redis.asyncio import Redis


class RedisReadinessChecker:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def is_ready(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False
