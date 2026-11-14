# 文件说明：后端自动化测试：test_skill_executor。
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from app.skills.executor import (
    SkillContext,
    SkillExecutionError,
    SkillExecutor,
)
from app.skills.manifest import SkillManifest
from app.tools.base import ToolLimitExceeded, ToolRunner
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.registry import ToolRegistry


class SkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class SkillOutput(BaseModel):
    value: str


def manifest(
    *,
    status: str = "active",
    allowed_tools: list[str] | None = None,
    allowed_mcp_connectors: list[str] | None = None,
    max_tool_calls: int = 1,
    timeout_seconds: float = 2.0,
) -> SkillManifest:
    return SkillManifest(
        name="route-optimization",
        version="1.0.0",
        status=status,  # type: ignore[arg-type]
        description="Build a feasible route order from verified places.",
        allowed_tools=allowed_tools or ["get_route"],
        allowed_mcp_connectors=allowed_mcp_connectors or [],
        max_tool_calls=max_tool_calls,
        timeout_seconds=timeout_seconds,
    )


def tool_context(
    *,
    max_calls: int = 2,
    allowed_mcp_connectors: set[str] | None = None,
) -> ToolContext:
    return ToolContext(
        runner=ToolRunner(
            max_calls=max_calls,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools={"get_route", "search_places"},
        provider_permissions={"map"},
        owner_id=uuid4(),
        allowed_mcp_connectors=allowed_mcp_connectors or set(),
    )


async def _unused_handler(_: ToolContext, __: BaseModel) -> BaseModel:
    return SkillOutput(value="unused")


def tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="get_route",
            description="Route fixture.",
            input_model=SkillInput,
            output_model=SkillOutput,
            provider_type="map",
        ),
        _unused_handler,
    )
    return registry


async def test_executor_rejects_disabled_skill() -> None:
    executor = SkillExecutor()

    with pytest.raises(SkillExecutionError) as caught:
        await executor.execute(
            manifest(status="disabled"),
            SkillContext(
                tool_registry=tool_registry(),
                tool_context=tool_context(),
            ),
            SkillInput(value="blocked"),
        )

    assert caught.value.code == "skill_disabled"


async def test_executor_scopes_registry_tools_and_returns_versioned_result() -> None:
    captured_tools: set[str] = set()

    async def handler(
        _: SkillManifest,
        context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        captured_tools.update(context.allowed_tools)
        return SkillOutput(value=SkillInput.model_validate(input_data).value)

    result = await SkillExecutor().execute(
        manifest(),
        SkillContext(
            tool_registry=tool_registry(),
            tool_context=tool_context(),
            handler=handler,
        ),
        SkillInput(value="typed"),
    )

    assert captured_tools == {"get_route"}
    assert result.skill_name == "route-optimization"
    assert result.version == "1.0.0"
    assert result.status == "completed"
    assert result.output == SkillOutput(value="typed")


async def test_executor_fails_when_manifest_tool_is_outside_context_allowlist() -> None:
    context = tool_context()
    scoped = ToolContext(
        runner=context.runner,
        allowed_tools={"search_places"},
        provider_permissions=context.provider_permissions,
        owner_id=context.owner_id,
    )

    with pytest.raises(SkillExecutionError) as caught:
        await SkillExecutor().execute(
            manifest(),
            SkillContext(tool_registry=tool_registry(), tool_context=scoped),
            SkillInput(value="blocked"),
        )

    assert caught.value.code == "skill_tool_not_allowed"


async def test_executor_enforces_skill_timeout() -> None:
    async def handler(
        _: SkillManifest,
        __: ToolContext,
        ___: BaseModel,
    ) -> BaseModel:
        await asyncio.sleep(0.1)
        return SkillOutput(value="late")

    with pytest.raises(SkillExecutionError) as caught:
        await SkillExecutor().execute(
            manifest(timeout_seconds=0.01),
            SkillContext(
                tool_registry=tool_registry(),
                tool_context=tool_context(),
                handler=handler,
            ),
            SkillInput(value="late"),
        )

    assert caught.value.code == "skill_timeout"


async def test_executor_scopes_tool_call_limit() -> None:
    async def handler(
        _: SkillManifest,
        context: ToolContext,
        __: BaseModel,
    ) -> BaseModel:
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        await context.runner.call(
            tool_name="get_route",
            provider="mock",
            input_payload={"step": 1},
            operation=operation,
        )
        await context.runner.call(
            tool_name="get_route",
            provider="mock",
            input_payload={"step": 2},
            operation=operation,
        )
        return SkillOutput(value=str(calls))

    with pytest.raises(ToolLimitExceeded):
        await SkillExecutor().execute(
            manifest(max_tool_calls=1),
            SkillContext(
                tool_registry=tool_registry(),
                tool_context=tool_context(max_calls=2),
                handler=handler,
            ),
            SkillInput(value="limit"),
        )


async def test_executor_scopes_mcp_connectors_before_handler() -> None:
    captured_connectors: set[str] = set()

    async def handler(
        _: SkillManifest,
        context: ToolContext,
        __: BaseModel,
    ) -> BaseModel:
        captured_connectors.update(context.allowed_mcp_connectors)
        return SkillOutput(value="scoped")

    result = await SkillExecutor().execute(
        manifest(allowed_mcp_connectors=["amap"]),
        SkillContext(
            tool_registry=tool_registry(),
            tool_context=tool_context(allowed_mcp_connectors={"amap", "weather"}),
            handler=handler,
        ),
        SkillInput(value="scoped"),
    )

    assert captured_connectors == {"amap"}
    assert result.allowed_tools == ("get_route",)


async def test_executor_rejects_connector_outside_context_allowlist() -> None:
    async def handler(
        _: SkillManifest,
        __: ToolContext,
        ___: BaseModel,
    ) -> BaseModel:
        return SkillOutput(value="must not run")

    with pytest.raises(SkillExecutionError) as caught:
        await SkillExecutor().execute(
            manifest(allowed_mcp_connectors=["amap"]),
            SkillContext(
                tool_registry=tool_registry(),
                tool_context=tool_context(allowed_mcp_connectors={"weather"}),
                handler=handler,
            ),
            SkillInput(value="blocked"),
        )

    assert caught.value.code == "skill_mcp_not_allowed"
