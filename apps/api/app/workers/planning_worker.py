# 文件说明：后台任务 Worker：planning_worker。
import asyncio
import logging
import sys
from collections.abc import Callable
from contextlib import suppress
from typing import Protocol
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.models.agent_run import AgentRun
from app.queue.planning_queue import PlanningQueue, RedisPlanningQueue
from app.services.planning_service import PlanningService, PlanningTripNotFoundError

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class SessionContext(Protocol):
    async def __aenter__(self) -> AsyncSession: ...

    async def __aexit__(self, *args: object) -> object: ...


SessionFactory = Callable[[], SessionContext]


async def requeue_unfinished_jobs(
    settings: Settings,
    *,
    queue: PlanningQueue | None = None,
    session_factory: SessionFactory | None = None,
) -> int:
    resolved_queue = queue or RedisPlanningQueue(settings)
    resolved_session_factory = session_factory or async_session_factory
    async with resolved_session_factory() as session:
        result = await session.execute(
            select(AgentRun.id).where(
                AgentRun.status.in_(["queued", "running"]),
                AgentRun.purpose == "planning",
                AgentRun.trip_id.is_not(None),
            )
        )
        job_ids = list(result.scalars())
    for job_id in job_ids:
        await resolved_queue.enqueue(job_id)
    return len(job_ids)


async def process_job(
    job_id: UUID,
    settings: Settings,
    checkpointer: AsyncPostgresSaver,
) -> None:
    async with async_session_factory() as session:
        service = PlanningService(
            session,
            settings,
            checkpointer=checkpointer,
        )
        await service.run_job(job_id)


async def planning_worker_loop(
    settings: Settings | None = None,
    ready_event: asyncio.Event | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    redis_client = Redis.from_url(
        resolved_settings.redis_url,
        decode_responses=True,
    )
    try:
        requeued = await requeue_unfinished_jobs(resolved_settings)
        if requeued:
            logger.info("Requeued %s unfinished planning jobs", requeued)
        async with AsyncPostgresSaver.from_conn_string(
            resolved_settings.postgres_checkpoint_url
        ) as checkpointer:
            await checkpointer.setup()
            if ready_event is not None:
                ready_event.set()
            while True:
                item = await redis_client.brpop(
                    resolved_settings.planning_queue_key,
                    timeout=2,
                )
                if item is None:
                    continue
                try:
                    payload = item[1]
                    raw_job_id = (
                        payload
                        if isinstance(payload, str)
                        else payload.decode()
                    )
                    job_id = UUID(raw_job_id)
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid planning queue payload")
                    continue
                lock_key = f"{resolved_settings.planning_queue_key}:lock:{job_id}"
                acquired = await redis_client.set(
                    lock_key,
                    "1",
                    nx=True,
                    ex=900,
                )
                if not acquired:
                    continue
                try:
                    await process_job(job_id, resolved_settings, checkpointer)
                except PlanningTripNotFoundError:
                    logger.warning("Planning job is no longer available: %s", job_id)
                except Exception:
                    logger.exception("Planning worker failed for job %s", job_id)
                finally:
                    await redis_client.delete(lock_key)
    finally:
        await redis_client.aclose()


async def main() -> None:
    settings = get_settings()
    try:
        await planning_worker_loop(settings)
    except asyncio.CancelledError:
        with suppress(asyncio.CancelledError):
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
