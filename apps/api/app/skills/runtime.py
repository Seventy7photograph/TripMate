# 文件说明：Skill 统一运行时：集中组装受控 Tool、handler 与完整性检查。
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.evidence.service import EvidenceService
from app.mcp.client import OfficialMcpClient
from app.mcp.gateway import McpGateway
from app.mcp.registry import McpConnectorRegistry
from app.mcp.tools import McpPlaceTool, McpWeatherTool
from app.providers.base import MapProvider, NearbyPlaceProvider
from app.services.feature_service import FeatureDisabledError, FeatureFlagService
from app.services.mcp_connector_service import McpConnectorService
from app.services.memory_service import MemoryService
from app.services.place_service import PlaceService, create_map_provider
from app.services.upload_service import UploadService
from app.skills.executor import (
    SkillContext,
    SkillExecutionResult,
    SkillExecutor,
    SkillHandler,
)
from app.skills.manifest import SkillManifest
from app.skills.production import production_skill_handlers
from app.skills.registry import SkillRegistry, load_configured_registry
from app.tools.altitude_tools import AltitudeTool, create_altitude_tool
from app.tools.attachment_tools import AttachmentTool
from app.tools.base import ToolRunner
from app.tools.budget_tools import BudgetTool
from app.tools.context import ToolContext
from app.tools.matrix_tools import MatrixTool
from app.tools.memory_tools import MemoryTool
from app.tools.nearby_tools import NearbyTool
from app.tools.place_detail_tools import PlaceDetailTool
from app.tools.place_fact_tools import PlaceFactTool
from app.tools.place_tools import PlaceTool
from app.tools.registry import ToolRegistry
from app.tools.route_tools import RouteTool
from app.tools.weather_tools import WeatherTool, create_weather_tool


@dataclass(frozen=True, slots=True)
class SkillRuntimeIntegrity:
    manifest_count: int
    missing_handlers: list[str]
    missing_tools: list[str]
    missing_mcp_connectors: list[str]


@dataclass(slots=True)
class SkillRuntime:
    registry: SkillRegistry
    tools: ToolRegistry
    tool_context: ToolContext
    handlers: dict[str, SkillHandler]
    executor: SkillExecutor
    selected_manifests: dict[str, SkillManifest] = field(default_factory=dict)
    mcp_gateway: McpGateway | None = None
    closeables: tuple[object, ...] = ()

    def manifest(self, name: str) -> SkillManifest:
        selected = self.selected_manifests.get(name)
        return selected if selected is not None else self.registry.get(name)

    def selected_manifest(self, name: str) -> SkillManifest:
        manifest = self.selected_manifests.get(name)
        if manifest is None:
            raise LookupError(f"Skill is not enabled for this run: {name}")
        return manifest

    async def execute(
        self,
        name: str,
        payload: BaseModel | dict[str, object],
        *,
        tool_context: ToolContext | None = None,
        max_tokens: int | None = None,
    ) -> SkillExecutionResult:
        manifest = self.manifest(name)
        if self.selected_manifests and name not in self.selected_manifests:
            raise LookupError(f"Skill is not enabled for this run: {name}")
        handler = self.handlers.get(name)
        if handler is None:
            raise LookupError(f"Skill handler is not registered: {name}")
        return await self.executor.execute(
            manifest,
            SkillContext(
                tool_registry=self.tools,
                tool_context=tool_context or self.tool_context,
                handler=handler,
            ),
            payload,
            max_tokens=max_tokens,
        )

    def integrity_report(self) -> SkillRuntimeIntegrity:
        manifests = self.registry.latest_manifests()
        missing_handlers = sorted(
            manifest.name
            for manifest in manifests
            if manifest.name not in self.handlers
        )
        missing_tools = sorted(
            {
                tool
                for manifest in manifests
                for tool in manifest.allowed_tools
                if tool not in self.tools.names
            }
        )
        missing_mcp_connectors = sorted(
            {
                connector
                for manifest in manifests
                for connector in manifest.allowed_mcp_connectors
                if connector not in {"amap", "weather"}
            }
        )
        return SkillRuntimeIntegrity(
            manifest_count=len(manifests),
            missing_handlers=missing_handlers,
            missing_tools=missing_tools,
            missing_mcp_connectors=missing_mcp_connectors,
        )

    async def close(self) -> None:
        seen: set[int] = set()
        for closeable in self.closeables:
            if id(closeable) in seen:
                continue
            seen.add(id(closeable))
            close = getattr(closeable, "close", None)
            if close is not None:
                await close()

    async def __aenter__(self) -> "SkillRuntime":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


async def build_skill_runtime(
    *,
    session: AsyncSession,
    settings: Settings,
    owner_id: UUID,
    trip_id: UUID | None = None,
    map_provider: MapProvider | None = None,
    weather_enabled: bool | None = None,
    max_tool_calls: int | None = None,
    deadline: datetime | None = None,
) -> SkillRuntime:
    provider = map_provider or create_map_provider(settings)
    weather_provider_enabled = (
        await FeatureFlagService(session).is_enabled("weather_provider")
        if weather_enabled is None
        else weather_enabled
    )
    connector_registry = McpConnectorRegistry(settings)
    configured_mcp = (
        connector_registry.configured_connectors
        if settings.mcp_gateway_enabled
        else frozenset()
    )
    runner = ToolRunner(
        max_calls=max_tool_calls or settings.planning_max_tool_calls,
        deadline=deadline
        or (
            datetime.now(UTC)
            + timedelta(seconds=settings.planning_timeout_seconds)
        ),
    )
    tool_context = ToolContext(
        runner=runner,
        allowed_tools={
            PlaceTool.name,
            RouteTool.name,
            BudgetTool.name,
            MemoryTool.name,
            WeatherTool.name,
            NearbyTool.name,
            PlaceDetailTool.name,
            PlaceFactTool.name,
            MatrixTool.name,
            AltitudeTool.name,
            AttachmentTool.name,
        },
        provider_permissions={
            "map",
            "deterministic",
            "memory",
            "weather",
            "attachment",
        },
        owner_id=owner_id,
        evidence_writer=EvidenceService(session),
        allowed_mcp_connectors=configured_mcp,
    )
    place_service = PlaceService(
        session,
        settings,
        provider=provider,
    )
    place_tool = PlaceTool(provider, tool_context)
    route_tool = RouteTool(provider, tool_context)
    budget_tool = BudgetTool(tool_context)
    memory_tool = MemoryTool(MemoryService(session), tool_context)
    weather_tool = (
        create_weather_tool(settings, tool_context)
        if weather_provider_enabled
        else None
    )
    nearby_tool = NearbyTool(
        cast(NearbyPlaceProvider, provider),
        tool_context,
    )
    place_detail_tool = PlaceDetailTool(place_service, tool_context)
    place_fact_tool = PlaceFactTool(place_service, tool_context)
    matrix_tool = MatrixTool(place_service, route_tool, tool_context)
    altitude_tool = (
        create_altitude_tool(settings, tool_context)
        if weather_provider_enabled
        else None
    )
    attachment_tool = AttachmentTool(
        UploadService(session, settings),
        tool_context,
    )
    local_tools = ToolRegistry()
    local_tools.register(PlaceTool.spec(), place_tool.invoke)
    local_tools.register(RouteTool.spec(), route_tool.invoke)
    local_tools.register(BudgetTool.spec(), budget_tool.invoke)
    local_tools.register(MemoryTool.spec(), memory_tool.invoke)
    local_tools.register(
        WeatherTool.spec(),
        weather_tool.invoke if weather_tool is not None else _disabled_tool,
    )
    local_tools.register(NearbyTool.spec(), nearby_tool.invoke)
    local_tools.register(PlaceDetailTool.spec(), place_detail_tool.invoke)
    local_tools.register(PlaceFactTool.spec(), place_fact_tool.invoke)
    local_tools.register(MatrixTool.spec(), matrix_tool.invoke)
    local_tools.register(
        AltitudeTool.spec(),
        altitude_tool.invoke if altitude_tool is not None else _disabled_tool,
    )
    local_tools.register(AttachmentTool.spec(), attachment_tool.invoke)

    gateway = (
        McpGateway(
            settings=settings,
            connector_registry=connector_registry,
            tool_registry=local_tools,
            client=OfficialMcpClient(),
            state_store=McpConnectorService(session, settings),
        )
        if configured_mcp
        else None
    )
    tools = local_tools
    if gateway is not None:
        tools = ToolRegistry()
        place_mcp = McpPlaceTool(gateway)
        weather_mcp = McpWeatherTool(gateway)
        for name in sorted(local_tools.names):
            spec = local_tools.get(name).spec
            if name == PlaceTool.name and "amap" in configured_mcp:
                tools.register(spec, place_mcp.invoke)
            elif (
                name == WeatherTool.name
                and weather_tool is not None
                and "weather" in configured_mcp
            ):
                tools.register(spec, weather_mcp.invoke)
            else:
                tools.register(spec, local_tools.get(name).handler)

    registry = load_configured_registry(settings)
    handlers = production_skill_handlers(tools, tool_context)
    return SkillRuntime(
        registry=registry,
        tools=tools,
        tool_context=tool_context,
        handlers=handlers,
        executor=SkillExecutor(),
        mcp_gateway=gateway,
        closeables=tuple(
            item
            for item in (provider, weather_tool, altitude_tool)
            if item is not None
        ),
    )


async def _disabled_tool(
    _: ToolContext,
    __: BaseModel,
) -> BaseModel:
    raise FeatureDisabledError("weather_provider")
