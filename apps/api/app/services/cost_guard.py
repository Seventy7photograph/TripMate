# 文件说明：业务服务：cost_guard。
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
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


def settled_cost_minor(
    *,
    reserved: int,
    reported: int,
    provider: str,
) -> int:
    if provider == "mock":
        return max(0, reported)
    # Unknown live pricing must not release a reserved daily budget.
    return max(reserved, reported)


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
        requested_cost_minor: int = 0,
    ) -> None:
        await self._lock_scopes(
            owner_id=owner_id,
            provider=provider,
            request_ip_hash=request_ip_hash,
        )
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
            requested=requested_cost_minor,
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
                requested=requested_cost_minor,
            )

        provider_spent = await self._sum(
            day_start,
            AgentRun.provider == provider,
        )
        self._raise_if_exceeded(
            scope="provider",
            spent=provider_spent,
            limit=self._settings.daily_provider_cost_limit_minor,
            requested=requested_cost_minor,
        )

    async def _lock_scopes(
        self,
        *,
        owner_id: UUID,
        provider: str,
        request_ip_hash: str | None,
    ) -> None:
        if self._session.bind is None:
            return
        if self._session.bind.dialect.name != "postgresql":
            return
        scopes = {
            f"user:{owner_id}",
            f"provider:{provider}",
        }
        if request_ip_hash is not None:
            scopes.add(f"ip:{request_ip_hash}")
        # Stable lock order prevents concurrent budget checks from deadlocking.
        for scope in sorted(scopes):
            await self._session.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtextextended(:scope, 0)"
                    ")"
                ),
                {"scope": scope},
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
        requested: int,
    ) -> None:
        if spent + requested > limit:
            raise CostLimitExceeded(
                scope=scope,
                limit_minor=limit,
                spent_minor=spent,
            )
