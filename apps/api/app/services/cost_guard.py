# 文件说明：业务服务：cost_guard。
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.models.agent_run import AgentRun


@dataclass(frozen=True, slots=True)
class CostLimitExceeded(Exception):
    scope: str
    limit_minor: int
    spent_minor: int

    def __str__(self) -> str:
        return f"{self.scope} daily cost limit exceeded"


def hash_client_ip(ip_address: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:{ip_address}".encode()).hexdigest()


class CostGuard:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def check(
        self,
        *,
        owner_id: UUID,
        provider: str,
        request_ip_hash: str | None,
    ) -> None:
        day_start = datetime.now(UTC).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        user_spent = await self._sum(
            day_start,
            AgentRun.created_by == owner_id,
        )
        self._raise_if_exceeded(
            scope="user",
            spent=user_spent,
            limit=self._settings.daily_user_cost_limit_minor,
        )

        if request_ip_hash is not None:
            ip_spent = await self._sum(
                day_start,
                AgentRun.request_ip_hash == request_ip_hash,
            )
            self._raise_if_exceeded(
                scope="ip",
                spent=ip_spent,
                limit=self._settings.daily_ip_cost_limit_minor,
            )

        provider_spent = await self._sum(
            day_start,
            AgentRun.provider == provider,
        )
        self._raise_if_exceeded(
            scope="provider",
            spent=provider_spent,
            limit=self._settings.daily_provider_cost_limit_minor,
        )

    async def _sum(
        self,
        day_start: datetime,
        condition: ColumnElement[bool],
    ) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(AgentRun.estimated_cost_minor), 0)).where(
                AgentRun.created_at >= day_start,
                condition,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    def _raise_if_exceeded(
        *,
        scope: str,
        spent: int,
        limit: int,
    ) -> None:
        if spent >= limit:
            raise CostLimitExceeded(
                scope=scope,
                limit_minor=limit,
                spent_minor=spent,
            )
