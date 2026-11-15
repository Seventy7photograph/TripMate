# 文件说明：将真实 Provider/Tool 结果写入 Admin 可消费的健康状态。
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_health import ProviderHealth
from app.tools.base import ToolCallAudit


class ProviderHealthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_audit(self, audit: ToolCallAudit) -> ProviderHealth:
        provider_key, provider_type = _provider_identity(audit.provider)
        return await self.record(
            provider_key=provider_key,
            provider_type=provider_type,
            provider_name=audit.provider,
            status="healthy" if audit.status == "success" else "degraded",
            latency_ms=audit.latency_ms,
            error_code=audit.error_code,
            details={"tool_name": audit.tool_name},
        )

    async def record_llm(
        self,
        *,
        provider_name: str,
        status: str,
        latency_ms: int,
        model_name: str,
        error_code: str | None = None,
    ) -> ProviderHealth:
        return await self.record(
            provider_key="llm_provider",
            provider_type="llm",
            provider_name=provider_name,
            status=status,
            latency_ms=latency_ms,
            error_code=error_code,
            details={"model_name": model_name},
        )

    async def record(
        self,
        *,
        provider_key: str,
        provider_type: str,
        provider_name: str,
        status: str,
        latency_ms: int,
        error_code: str | None = None,
        details: dict[str, object] | None = None,
    ) -> ProviderHealth:
        model = await self._session.scalar(
            select(ProviderHealth).where(
                ProviderHealth.provider_key == provider_key
            )
        )
        if model is None:
            model = ProviderHealth(provider_key=provider_key)
            self._session.add(model)
        model.provider_type = provider_type
        model.provider_name = provider_name[:40]
        model.status = status
        model.latency_ms = max(0, latency_ms)
        model.error_code = (
            error_code[:80] if error_code is not None else None
        )
        model.details = dict(details or {})
        model.checked_at = datetime.now(UTC)
        await self._session.flush()
        return model


def _provider_identity(provider: str) -> tuple[str, str]:
    normalized = provider.strip().lower()
    if normalized in {"amap", "mcp:amap"}:
        return "map_provider", "map"
    if normalized in {
        "amap-weather",
        "open-meteo",
        "mcp:weather",
        "weather",
    }:
        return "weather_provider", "weather"
    return f"tool:{normalized[:50]}", "tool"
