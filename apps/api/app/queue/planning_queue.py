# 文件说明：后台队列：planning_queue。
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings


class PlanningQueue(Protocol):
    is_inline: bool

    async def enqueue(self, job_id: UUID) -> None: ...


class InlinePlanningQueue:
    """Test-only queue that lets PlanningService execute the job in-process."""

    is_inline = True

    async def enqueue(self, job_id: UUID) -> None:
        del job_id


class RedisPlanningQueue:
    is_inline = False

    def __init__(self, settings: Settings) -> None:
        self._redis_url = settings.redis_url
        self._queue_key = settings.planning_queue_key

    async def enqueue(self, job_id: UUID) -> None:
        client = Redis.from_url(self._redis_url, decode_responses=True)
        try:
            await client.lpush(self._queue_key, str(job_id))
        finally:
            await client.aclose()


def create_planning_queue(settings: Settings) -> PlanningQueue:
    if settings.app_env == "test":
        return InlinePlanningQueue()
    return RedisPlanningQueue(settings)
