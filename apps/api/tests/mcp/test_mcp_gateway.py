# 文件说明：MCP Gateway 限额与调用测试。

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.mcp.gateway import McpGateway, McpNotAllowedError, McpTransportError
from app.mcp.models import McpConnectionState, McpToolResult
from app.mcp.registry import McpConnectorRegistry
from app.providers.mock_map import MockMapProvider
from app.tools.base import ToolLimitExceeded, ToolRunner
from app.tools.context import ToolContext
from app.tools.place_tools import PlaceTool
from app.tools.registry import ToolRegistry


class EnabledConnectorState:
    async def is_enabled(self, connector_id: str) -> bool:
        del connector_id
        return True

    async def authorize_call(self, connector_id: str) -> None:
        del connector_id

    async def record_success(
        self,
        connector_id: str,
        *,
        latency_ms: int,
    ) -> McpConnectionState:
        del connector_id
        return McpConnectionState(
            connector_id="amap",
            enabled=True,
            status="healthy",
            latency_ms=latency_ms,
            checked_at=datetime.now(UTC),
            daily_quota=100,
        )

    async def record_failure(
        self,
        connector_id: str,
        *,
        error_code: str,
    ) -> McpConnectionState:
        del connector_id
        return McpConnectionState(
            connector_id="amap",
            enabled=True,
            status="unavailable",
            latency_ms=0,
            last_error_code=error_code,
            checked_at=datetime.now(UTC),
            daily_quota=100,
        )


class NeverCalledClient:
    async def call_tool(self, **kwargs: object) -> object:
        del kwargs
        raise AssertionError("MCP client must not be called when the budget is zero")


class FailingClient:
    async def call_tool(self, **kwargs: object) -> object:
        del kwargs
        raise McpTransportError("connector unavailable")

    async def check_health(self, **kwargs: object) -> McpConnectionState:
        del kwargs
        raise McpTransportError("connector unavailable")


def gateway_with(context: ToolContext) -> McpGateway:
    settings = Settings(
        app_env="test",
        mcp_gateway_enabled=True,
        mcp_allowed_connectors="amap",
        mcp_amap_endpoint="https://mcp.example.test/amap",
    )
    tools = ToolRegistry()
    provider = MockMapProvider()
    tools.register(PlaceTool.spec(), PlaceTool(provider, context).invoke)
    return McpGateway(
        settings=settings,
        connector_registry=McpConnectorRegistry(settings),
        tool_registry=tools,
        client=cast(object, NeverCalledClient()),  # type: ignore[arg-type]
        state_store=EnabledConnectorState(),
    )


def gateway_with_client(
    context: ToolContext,
    client: object,
) -> McpGateway:
    settings = Settings(
        app_env="test",
        mcp_gateway_enabled=True,
        mcp_allowed_connectors="amap",
        mcp_amap_endpoint="https://mcp.example.test/amap",
    )
    tools = ToolRegistry()
    provider = MockMapProvider()
    tools.register(PlaceTool.spec(), PlaceTool(provider, context).invoke)
    return McpGateway(
        settings=settings,
        connector_registry=McpConnectorRegistry(settings),
        tool_registry=tools,
        client=cast(object, client),  # type: ignore[arg-type]
        state_store=EnabledConnectorState(),
    )


def tool_context(*, max_calls: int) -> ToolContext:
    return ToolContext(
        runner=ToolRunner(
            max_calls=max_calls,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools={"search_places"},
        allowed_mcp_connectors={"amap"},
        provider_permissions={"map"},
        owner_id=uuid4(),
    )


async def test_mcp_tool_uses_same_tool_runner_limit() -> None:
    context = tool_context(max_calls=0)
    gateway = gateway_with(context)

    with pytest.raises(ToolLimitExceeded):
        await gateway.call_tool(
            context,
            "amap",
            "search_places",
            {"keyword": "开元寺"},
        )


async def test_mcp_gateway_rejects_unallowlisted_connect_url() -> None:
    context = tool_context(max_calls=1)
    gateway = gateway_with(context)

    with pytest.raises(McpNotAllowedError):
        await gateway.connect("https://evil.example/mcp")


async def test_mcp_transport_failure_falls_back_to_existing_provider_tool() -> None:
    context = tool_context(max_calls=5)
    gateway = gateway_with_client(context, FailingClient())

    result = await gateway.call_tool(
        context,
        "amap",
        "search_places",
        {"keyword": "开元寺", "city": "泉州", "limit": 1},
    )

    assert isinstance(result, McpToolResult)
    assert result.fallback_used is True
    assert "开元寺" in result.data["results"][0]["name"]  # type: ignore[index]
    assert context.runner.call_count == 2
