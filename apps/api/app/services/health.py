# 文件说明：业务服务：health。
import asyncio
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings

logger = logging.getLogger(__name__)

HealthValue = Literal["ok", "error"]


@dataclass(frozen=True)
class HealthReport:
    database: HealthValue
    redis: HealthValue

    @property
    def healthy(self) -> bool:
        return self.database == "ok" and self.redis == "ok"


class HealthChecker(Protocol):
    async def check(self) -> HealthReport: ...


class InfrastructureHealthService:
    def __init__(self, settings: Settings) -> None:
        self._database_url = settings.database_url
        self._redis_url = settings.redis_url
        self._timeout_seconds = settings.health_check_timeout_seconds

    async def check(self) -> HealthReport:
        database, redis = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
        )
        return HealthReport(database=database, redis=redis)

    async def _check_database(self) -> HealthValue:
        engine = create_async_engine(self._database_url, pool_pre_ping=True)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
            return "ok"
        except Exception as exc:
            logger.warning("Database health check failed: %s", type(exc).__name__)
            return "error"
        finally:
            await engine.dispose()

    async def _check_redis(self) -> HealthValue:
        client: Redis = Redis.from_url(
            self._redis_url,
            socket_connect_timeout=self._timeout_seconds,
            socket_timeout=self._timeout_seconds,
        )
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await client.ping()
            return "ok"
        except Exception as exc:
            logger.warning("Redis health check failed: %s", type(exc).__name__)
            return "error"
        finally:
            await client.aclose()

