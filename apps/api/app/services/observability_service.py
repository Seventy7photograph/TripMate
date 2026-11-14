# 文件说明：业务服务：observability_service。
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import and_, case, func, select, true, type_coerce
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.config import Settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.agent_run import AgentRun
from app.models.provider_health import ProviderHealth
from app.models.tool_call_log import ToolCallLog
from app.schemas.admin import (
    AdminAgentRunListResponse,
    AdminAgentRunResponse,
    AdminAuditLogListResponse,
    AdminAuditLogResponse,
    AdminCostSummaryResponse,
    AdminProviderListResponse,
    AdminProviderResponse,
    AdminToolHealthListResponse,
    AdminToolHealthResponse,
    CostBreakdownItem,
    CostLimitsResponse,
    DailyCostItem,
    FeatureFlagKey,
    ModelConfigResponse,
    ProviderDisplayStatus,
)
from app.services.feature_service import FeatureFlagService
from app.services.model_config_service import ModelConfigService


class ObservabilityService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._features = FeatureFlagService(session)

    async def list_agent_runs(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None,
        purpose: str | None,
        provider: str | None,
    ) -> AdminAgentRunListResponse:
        filters = [AgentRun.provider != "mock"]
        if status:
            filters.append(AgentRun.status == status)
        if purpose:
            filters.append(AgentRun.purpose == purpose)
        if provider:
            filters.append(AgentRun.provider == provider)

        total = int(
            await self._session.scalar(
                select(func.count()).select_from(AgentRun).where(*filters)
            )
            or 0
        )
        result = await self._session.execute(
            select(AgentRun)
            .where(*filters)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return AdminAgentRunListResponse(
            items=[
                AdminAgentRunResponse.model_validate(run)
                for run in result.scalars()
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def cost_summary(self, *, days: int) -> AdminCostSummaryResponse:
        start_at = datetime.now(UTC) - timedelta(days=days)
        filtered = and_(
            AgentRun.created_at >= start_at,
            AgentRun.provider != "mock",
        )
        totals = (
            await self._session.execute(
                select(
                    func.count(AgentRun.id),
                    func.count(
                        case(
                            (AgentRun.status == "failed", AgentRun.id),
                            else_=None,
                        )
                    ),
                    func.coalesce(func.sum(AgentRun.input_tokens), 0),
                    func.coalesce(func.sum(AgentRun.output_tokens), 0),
                    func.coalesce(func.sum(AgentRun.estimated_cost_minor), 0),
                    func.coalesce(func.avg(AgentRun.latency_ms), 0),
                ).where(filtered)
            )
        ).one()
        by_provider = await self._breakdown(AgentRun.provider, start_at)
        by_model = await self._breakdown(AgentRun.model_name, start_at)
        by_skill = await self._skill_breakdown(start_at)
        daily_rows = (
            await self._session.execute(
                select(
                    func.date(AgentRun.created_at).label("day"),
                    func.count(AgentRun.id),
                    func.coalesce(func.sum(AgentRun.estimated_cost_minor), 0),
                )
                .where(filtered)
                .group_by("day")
                .order_by("day")
            )
        ).all()
        return AdminCostSummaryResponse(
            window_days=days,
            total_runs=int(totals[0]),
            failed_runs=int(totals[1]),
            total_input_tokens=int(totals[2]),
            total_output_tokens=int(totals[3]),
            total_cost_minor=int(totals[4]),
            average_latency_ms=int(totals[5]),
            by_provider=by_provider,
            by_model=by_model,
            by_skill=by_skill,
            daily=[
                DailyCostItem(
                    date=row.day,
                    runs=int(row[1]),
                    cost_minor=int(row[2]),
                )
                for row in daily_rows
            ],
            limits=CostLimitsResponse(
                user_daily_cost_minor=self._settings.daily_user_cost_limit_minor,
                ip_daily_cost_minor=self._settings.daily_ip_cost_limit_minor,
                provider_daily_cost_minor=(
                    self._settings.daily_provider_cost_limit_minor
                ),
                run_cost_minor=self._settings.planning_max_cost_minor,
                warning_ratio=self._settings.cost_warning_ratio,
            ),
        )

    async def providers(self) -> AdminProviderListResponse:
        flags = {
            flag.key: flag.enabled
            for flag in await self._features.list_flags()
        }
        health_rows = list(
            (await self._session.execute(select(ProviderHealth))).scalars()
        )
        health = {item.provider_key: item for item in health_rows}
        stats_start = datetime.now(UTC) - timedelta(hours=24)
        stats_rows = (
            await self._session.execute(
                select(
                    ToolCallLog.provider,
                    func.count(ToolCallLog.id),
                    func.count(
                        case(
                            (ToolCallLog.status != "success", ToolCallLog.id),
                            else_=None,
                        )
                    ),
                    func.coalesce(func.avg(ToolCallLog.latency_ms), 0),
                )
                .where(ToolCallLog.created_at >= stats_start)
                .group_by(ToolCallLog.provider)
            )
        ).all()
        stats = {
            str(row[0]): {
                "invocations": int(row[1]),
                "failed": int(row[2]),
                "average_latency": int(row[3]),
            }
            for row in stats_rows
        }
        model_configs = await ModelConfigService(
            self._session,
            self._settings,
        ).list_configs()
        definitions = self._provider_definitions(model_configs)
        items: list[AdminProviderResponse] = []
        for key, provider_type, provider_name, profile, configured, configuration in (
            definitions
        ):
            enabled = flags[key]
            latest = health.get(key)
            provider_stats = (
                stats.get(provider_name, {})
                if provider_type == "map"
                else _aggregate_provider_stats(
                    stats,
                    ("amap-weather", "open-meteo"),
                )
                if key == "weather_provider"
                else {}
            )
            if not enabled:
                status = "disabled"
            elif latest is not None:
                status = latest.status
            elif configured:
                status = "configured"
            else:
                status = "unavailable"
            items.append(
                AdminProviderResponse(
                    key=key,
                    provider_type=provider_type,
                    provider_name=provider_name,
                    profile=profile,
                    configured=configured,
                    enabled=enabled,
                    status=cast(
                        ProviderDisplayStatus,
                        status,
                    ),
                    latency_ms=latest.latency_ms if latest is not None else 0,
                    invocations=int(provider_stats.get("invocations", 0)),
                    failed_invocations=int(provider_stats.get("failed", 0)),
                    average_latency_ms=int(
                        provider_stats.get("average_latency", 0)
                    ),
                    last_error_code=None if latest is None else latest.error_code,
                    last_checked_at=None if latest is None else latest.checked_at,
                    configuration=configuration,
                )
            )
        return AdminProviderListResponse(items=items)

    async def tool_health(self, *, hours: int) -> AdminToolHealthListResponse:
        start_at = datetime.now(UTC) - timedelta(hours=hours)
        rows = (
            await self._session.execute(
                select(
                    ToolCallLog.tool_name,
                    ToolCallLog.provider,
                    func.count(ToolCallLog.id),
                    func.count(
                        case(
                            (ToolCallLog.status != "success", ToolCallLog.id),
                            else_=None,
                        )
                    ),
                    func.coalesce(func.avg(ToolCallLog.latency_ms), 0),
                    func.max(ToolCallLog.created_at),
                )
                .where(ToolCallLog.created_at >= start_at)
                .group_by(ToolCallLog.tool_name, ToolCallLog.provider)
                .order_by(ToolCallLog.tool_name, ToolCallLog.provider)
            )
        ).all()
        errors = (
            await self._session.execute(
                select(
                    ToolCallLog.tool_name,
                    ToolCallLog.provider,
                    ToolCallLog.error_code,
                )
                .where(
                    ToolCallLog.created_at >= start_at,
                    ToolCallLog.status != "success",
                )
                .order_by(ToolCallLog.created_at.desc())
            )
        ).all()
        last_error = {
            (str(row[0]), str(row[1])): row[2]
            for row in errors
        }
        items: list[AdminToolHealthResponse] = []
        for row in rows:
            invocations = int(row[2])
            failed = int(row[3])
            status = (
                "healthy"
                if failed == 0
                else "unavailable"
                if failed >= invocations
                else "degraded"
            )
            items.append(
                AdminToolHealthResponse(
                    tool_name=str(row[0]),
                    provider=str(row[1]),
                    status=cast(ProviderDisplayStatus, status),
                    invocations=invocations,
                    failed_invocations=failed,
                    average_latency_ms=int(row[4]),
                    last_error_code=last_error.get((str(row[0]), str(row[1]))),
                    checked_at=row[5],
                )
            )
        return AdminToolHealthListResponse(items=items)

    async def audit_logs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> AdminAuditLogListResponse:
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(AdminAuditLog)
            )
            or 0
        )
        result = await self._session.execute(
            select(AdminAuditLog)
            .order_by(AdminAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return AdminAuditLogListResponse(
            items=[
                AdminAuditLogResponse.model_validate(item)
                for item in result.scalars()
            ],
            total=total,
        )

    async def _breakdown(
        self,
        key_column: InstrumentedAttribute[str],
        start_at: datetime,
    ) -> list[CostBreakdownItem]:
        rows = (
            await self._session.execute(
                select(
                    key_column,
                    func.count(AgentRun.id),
                    func.count(
                        case(
                            (AgentRun.status == "failed", AgentRun.id),
                            else_=None,
                        )
                    ),
                    func.coalesce(func.sum(AgentRun.input_tokens), 0),
                    func.coalesce(func.sum(AgentRun.output_tokens), 0),
                    func.coalesce(func.sum(AgentRun.estimated_cost_minor), 0),
                )
                .where(
                    and_(
                        AgentRun.created_at >= start_at,
                        AgentRun.provider != "mock",
                    )
                )
                .group_by(key_column)
                .order_by(func.sum(AgentRun.estimated_cost_minor).desc())
            )
        ).all()
        return [
            CostBreakdownItem(
                key=str(row[0]),
                runs=int(row[1]),
                failed_runs=int(row[2]),
                input_tokens=int(row[3]),
                output_tokens=int(row[4]),
                cost_minor=int(row[5]),
            )
            for row in rows
        ]

    async def _skill_breakdown(
        self,
        start_at: datetime,
    ) -> list[CostBreakdownItem]:
        skills = (
            func.jsonb_array_elements(AgentRun.skills_used)
            .table_valued("value")
            .alias("skill_rows")
        )
        skill_name = type_coerce(skills.c.value, JSONB)["name"].astext
        skill_count = func.jsonb_array_length(AgentRun.skills_used)
        rows = (
            await self._session.execute(
                select(
                    skill_name.label("key"),
                    func.count(func.distinct(AgentRun.id)),
                    func.count(
                        func.distinct(
                            case(
                                (AgentRun.status == "failed", AgentRun.id),
                                else_=None,
                            )
                        )
                    ),
                    func.coalesce(
                        func.sum(AgentRun.input_tokens / skill_count),
                        0,
                    ),
                    func.coalesce(
                        func.sum(AgentRun.output_tokens / skill_count),
                        0,
                    ),
                    func.coalesce(
                        func.sum(AgentRun.estimated_cost_minor / skill_count),
                        0,
                    ),
                )
                .select_from(AgentRun)
                .join(skills, true())
                .where(
                    AgentRun.created_at >= start_at,
                    AgentRun.provider != "mock",
                )
                .group_by(skill_name)
                .order_by(
                    func.sum(
                        AgentRun.estimated_cost_minor / skill_count
                    ).desc()
                )
            )
        ).all()
        return [
            CostBreakdownItem(
                key=str(row[0]),
                runs=int(row[1]),
                failed_runs=int(row[2]),
                input_tokens=int(row[3]),
                output_tokens=int(row[4]),
                cost_minor=int(row[5]),
            )
            for row in rows
            if row[0]
        ]

    def _provider_definitions(
        self,
        model_configs: list[ModelConfigResponse],
    ) -> list[
        tuple[
            FeatureFlagKey,
            str,
            str,
            str,
            bool,
            dict[str, object],
        ]
    ]:
        llm_configured = all(
            item.provider_profile == "live"
            and item.api_key_configured
            and bool(item.model_name.strip())
            for item in model_configs
        )
        llm_profiles = {item.provider_profile for item in model_configs}
        llm_profile = (
            "live"
            if llm_profiles == {"live"}
            else "mock"
            if llm_profiles == {"mock"}
            else "mixed"
        )
        map_configured = (
            self._settings.effective_map_provider_profile == "mock"
            or self._settings.amap_web_service_key is not None
        )
        weather_primary = (
            "amap-weather"
            if (
                self._settings.effective_map_provider_profile == "live"
                and self._settings.amap_web_service_key is not None
            )
            else "open-meteo"
        )
        weather_configured = (
            weather_primary == "amap-weather"
            or self._settings.weather_fallback_enabled
        )
        weather_provider_name = (
            "amap-weather+open-meteo"
            if (
                weather_primary == "amap-weather"
                and self._settings.weather_fallback_enabled
            )
            else weather_primary
        )
        return [
            (
                "llm_provider",
                "llm",
                "per-stage",
                llm_profile,
                llm_configured,
                {
                    "profile": llm_profile,
                    "configured": llm_configured,
                    "stages": [
                        {
                            "stage": item.stage,
                            "provider_profile": item.provider_profile,
                            "model_name": item.model_name,
                            "api_key_configured": item.api_key_configured,
                            "source": item.source,
                        }
                        for item in model_configs
                    ],
                },
            ),
            (
                "map_provider",
                "map",
                (
                    "mock"
                    if self._settings.effective_map_provider_profile == "mock"
                    else "amap"
                ),
                self._settings.effective_map_provider_profile,
                map_configured,
                {
                    "profile": self._settings.effective_map_provider_profile,
                    "configured": map_configured,
                    "timeout_seconds": self._settings.provider_timeout_seconds,
                },
            ),
            (
                "weather_provider",
                "weather",
                weather_provider_name,
                self._settings.effective_map_provider_profile,
                weather_configured,
                {
                    "primary": weather_primary,
                    "fallback_enabled": self._settings.weather_fallback_enabled,
                    "forecast_endpoint": self._settings.open_meteo_base_url,
                    "geocoding_endpoint": (
                        self._settings.open_meteo_geocoding_base_url
                    ),
                    "elevation_endpoint": (
                        self._settings.open_meteo_elevation_base_url
                    ),
                    "amap_weather_configured": (
                        self._settings.amap_web_service_key is not None
                    ),
                    "timeout_seconds": self._settings.provider_timeout_seconds,
                },
            ),
        ]


def _aggregate_provider_stats(
    stats: dict[str, dict[str, int]],
    providers: tuple[str, ...],
) -> dict[str, int]:
    return {
        "invocations": sum(
            stats.get(provider, {}).get("invocations", 0)
            for provider in providers
        ),
        "failed": sum(
            stats.get(provider, {}).get("failed", 0)
            for provider in providers
        ),
        "average_latency": max(
            (
                stats.get(provider, {}).get("average_latency", 0)
                for provider in providers
            ),
            default=0,
        ),
    }
