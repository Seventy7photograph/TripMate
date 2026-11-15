# 文件说明：业务服务：MCP connector 状态、配额与健康。

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.mcp.gateway import McpNotAllowedError
from app.mcp.models import McpConnectionState, McpConnectorStatus
from app.models.admin_audit_log import AdminAuditLog
from app.models.mcp_connector import McpConnectorState as McpConnectorStateModel
from app.services.feature_service import FeatureFlagService
from app.skills.metadata import MCP_METADATA


class McpConnectorNotFoundError(Exception):
    pass


class McpQuotaExceededError(McpNotAllowedError):
    pass


class McpConnectorService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._features = FeatureFlagService(session)

    async def list_connectors(self) -> list[McpConnectionState]:
        rows = list(
            (
                await self._session.execute(select(McpConnectorStateModel))
            ).scalars()
        )
        by_id = {row.connector_id: row for row in rows}
        return [
            self._view(connector_id, by_id.get(connector_id))
            for connector_id in ("amap", "weather")
        ]

    async def set_enabled(
        self,
        *,
        connector_id: str,
        enabled: bool,
        actor_id: UUID,
        reason: str | None,
    ) -> McpConnectionState:
        if connector_id not in {"amap", "weather"}:
            raise McpConnectorNotFoundError(connector_id)
        model = await self._session.get(McpConnectorStateModel, connector_id)
        previous = False if model is None else model.enabled
        if model is None:
            model = self._new_model(connector_id)
            self._session.add(model)
        model.enabled = enabled
        model.status = "configured" if enabled else "disabled"
        model.updated_by = actor_id
        self._session.add(
            AdminAuditLog(
                actor_id=actor_id,
                action="mcp_connector.toggle",
                target_type="mcp_connector",
                target_id=connector_id,
                details={
                    "previous_enabled": previous,
                    "enabled": enabled,
                    "reason": reason,
                },
            )
        )
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return self._view(connector_id, model)

    async def is_enabled(self, connector_id: str) -> bool:
        if not await self._features.is_enabled("mcp_gateway_enabled"):
            return False
        model = await self._session.get(McpConnectorStateModel, connector_id)
        return model is not None and model.enabled

    async def authorize_call(self, connector_id: str) -> None:
        if not await self._features.is_enabled("mcp_gateway_enabled"):
            raise McpNotAllowedError(connector_id)
        result = await self._session.execute(
            select(McpConnectorStateModel)
            .where(McpConnectorStateModel.connector_id == connector_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None or not model.enabled:
            raise McpNotAllowedError(connector_id)
        now = datetime.now(UTC)
        today = now.date()
        if model.quota_reset_at != today:
            model.quota_reset_at = today
            model.requests_today = 0
        if (
            model.window_started_at is None
            or now - model.window_started_at >= timedelta(minutes=1)
        ):
            model.window_started_at = now
            model.window_calls = 0
        if (
            model.requests_today >= model.daily_quota
            or model.window_calls >= model.rate_limit_per_minute
        ):
            raise McpQuotaExceededError(connector_id)
        model.requests_today += 1
        model.window_calls += 1
        await self._session.flush()

    async def record_success(
        self,
        connector_id: str,
        *,
        latency_ms: int,
    ) -> McpConnectionState:
        model = await self._get_or_create(connector_id)
        model.status = "healthy"
        model.latency_ms = max(0, latency_ms)
        model.last_error_code = None
        model.checked_at = datetime.now(UTC)
        await self._session.flush()
        return self._view(connector_id, model)

    async def record_failure(
        self,
        connector_id: str,
        *,
        error_code: str,
    ) -> McpConnectionState:
        model = await self._get_or_create(connector_id)
        model.status = "unavailable"
        model.last_error_code = error_code[:80]
        model.checked_at = datetime.now(UTC)
        await self._session.flush()
        return self._view(connector_id, model)

    async def record_fallback(
        self,
        connector_id: str,
        *,
        error_code: str,
    ) -> McpConnectionState:
        model = await self._get_or_create(connector_id)
        model.status = "degraded"
        model.last_error_code = error_code[:80]
        model.checked_at = datetime.now(UTC)
        await self._session.flush()
        return self._view(connector_id, model)

    async def _get_or_create(self, connector_id: str) -> McpConnectorStateModel:
        model = await self._session.get(McpConnectorStateModel, connector_id)
        if model is not None:
            return model
        model = self._new_model(connector_id)
        self._session.add(model)
        await self._session.flush()
        return model

    def _new_model(self, connector_id: str) -> McpConnectorStateModel:
        return McpConnectorStateModel(
            connector_id=connector_id,
            enabled=False,
            status="disabled",
            latency_ms=0,
            daily_quota=self._settings.mcp_daily_quota_per_connector,
            requests_today=0,
            rate_limit_per_minute=self._settings.mcp_rate_limit_per_minute,
            window_calls=0,
        )

    def _view(
        self,
        connector_id: str,
        model: McpConnectorStateModel | None,
    ) -> McpConnectionState:
        today = datetime.now(UTC).date()
        status = "disabled"
        if model is not None:
            if model.enabled:
                status = model.status
                if status == "disabled":
                    status = "configured"
            elif model.status in {"healthy", "unavailable", "degraded"}:
                status = model.status
        metadata = MCP_METADATA.get(
            connector_id,
            MCP_METADATA["amap"],
        )
        endpoint = (
            self._settings.mcp_amap_endpoint
            if connector_id == "amap"
            else self._settings.mcp_weather_endpoint
        )
        return McpConnectionState(
            connector_id=connector_id,
            display_name=metadata.display_name,
            purpose=metadata.purpose,
            boundary=metadata.boundary,
            tools=list(metadata.tools),
            configured=(
                connector_id in self._settings.mcp_allowed_connector_list
                and bool(endpoint)
            ),
            enabled=model is not None and model.enabled,
            status=cast(McpConnectorStatus, status),
            latency_ms=0 if model is None else model.latency_ms,
            last_error_code=(
                None if model is None else model.last_error_code
            ),
            checked_at=None if model is None else model.checked_at,
            requests_today=(
                0
                if model is None or model.quota_reset_at != today
                else model.requests_today
            ),
            daily_quota=(
                self._settings.mcp_daily_quota_per_connector
                if model is None
                else model.daily_quota
            ),
            rate_limit_per_minute=(
                self._settings.mcp_rate_limit_per_minute
                if model is None
                else model.rate_limit_per_minute
            ),
            window_calls=0 if model is None else model.window_calls,
            as_of=datetime.now(UTC),
        )
