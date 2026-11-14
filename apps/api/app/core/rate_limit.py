# 文件说明：核心基础设施：rate_limit。
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from redis.asyncio import Redis


class RedisRateLimitClient(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> None: ...

    async def ttl(self, key: str) -> int: ...


@dataclass(frozen=True, slots=True)
class RateLimitExceeded(Exception):
    retry_after_seconds: int

    def __str__(self) -> str:
        return "rate limit exceeded"


class RateLimiter:
    def __init__(self, redis: Any) -> None:
        self._redis: RedisRateLimitClient = redis

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> None:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window_seconds)
        if count <= limit:
            return
        ttl = await self._redis.ttl(key)
        raise RateLimitExceeded(
            retry_after_seconds=max(1, min(ttl, window_seconds)),
        )


@lru_cache
def get_redis_client(url: str) -> Redis:
    return Redis.from_url(url, decode_responses=True)
