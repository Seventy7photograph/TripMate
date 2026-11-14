# 文件说明：后端自动化测试：test_tool_registry。
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.providers.mock_map import MockMapProvider
from app.tools.base import ToolRunner
from app.tools.budget_tools import BudgetTool, BudgetToolInput
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.place_tools import PlaceTool, SearchPlacesInput
from app.tools.registry import ToolNotAllowedError, ToolRegistry
from app.tools.route_tools import GetRouteInput, RouteTool, RouteToolOutput


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class EchoOutput(BaseModel):
    value: str


async def _echo_handler(
    context: ToolContext,
    payload: BaseModel,
) -> BaseModel:
    del context
    request = EchoInput.model_validate(payload)
    return EchoOutput(value=request.value)


def _tool_context() -> ToolContext:
    return ToolContext(
        runner=ToolRunner(
            max_calls=3,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools=frozenset({"echo"}),
        provider_permissions=frozenset({"deterministic"}),
        owner_id=uuid4(),
    )


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            description="Echo the input value.",
            input_model=EchoInput,
            output_model=EchoOutput,
            provider_type="deterministic",
        ),
        _echo_handler,
    )
    return registry


async def test_registry_rejects_unknown_tool() -> None:
    registry = ToolRegistry()

    with pytest.raises(ToolNotAllowedError):
        await registry.invoke(_tool_context(), "shell_exec", {})


async def test_registry_rejects_registered_tool_outside_allowlist() -> None:
    context = ToolContext(
        runner=_tool_context().runner,
        allowed_tools=frozenset(),
        provider_permissions=frozenset({"deterministic"}),
        owner_id=uuid4(),
    )

    with pytest.raises(ToolNotAllowedError):
        await _registry().invoke(context, "echo", {"value": "blocked"})


async def test_registry_validates_input_and_output_models() -> None:
    registry = _registry()

    with pytest.raises(ValidationError):
        await registry.invoke(
            _tool_context(),
            "echo",
            {"value": "allowed", "shell": "rm -rf /"},
        )

    result = await registry.invoke(_tool_context(), "echo", {"value": "typed"})

    assert isinstance(result, EchoOutput)
    assert result.value == "typed"


def test_openai_schema_only_contains_registered_allowlisted_tools() -> None:
    registry = _registry()
    schemas = registry.openai_schemas({"echo", "get_weather"})

    assert registry.names == frozenset({"echo"})
    assert [item.name for item in schemas] == ["echo"]
    assert schemas[0].parameters["additionalProperties"] is False


def test_place_tool_schema_exposes_search_filters() -> None:
    schema = SearchPlacesInput.model_json_schema()

    assert set(schema["properties"]) == {"keyword", "city", "types", "limit"}
    assert PlaceTool.spec().input_model is SearchPlacesInput


def test_route_tool_schema_contains_supported_modes() -> None:
    schema = GetRouteInput.model_json_schema()
    mode_schema = schema["properties"]["mode"]

    assert {
        "walking",
        "driving",
        "bicycling",
        "bus",
        "subway",
        "flight",
    } <= set(mode_schema["enum"])
    assert RouteTool.spec().input_model is GetRouteInput


def test_budget_tool_uses_integer_minor_units() -> None:
    schema = BudgetToolInput.model_json_schema()
    costs = schema["properties"]["stop_costs_minor"]

    assert costs["items"]["type"] == "integer"
    assert costs["items"]["minimum"] == 0
    assert BudgetTool.spec().input_model is BudgetToolInput


async def test_registry_invokes_current_place_and_route_tools() -> None:
    runner = ToolRunner(
        max_calls=5,
        deadline=datetime.now(UTC) + timedelta(seconds=10),
    )
    context = ToolContext(
        runner=runner,
        allowed_tools={"search_places", "get_route"},
        provider_permissions={"map"},
        owner_id=uuid4(),
    )
    provider = MockMapProvider()
    place_tool = PlaceTool(provider, context)
    route_tool = RouteTool(provider, context)
    registry = ToolRegistry()
    registry.register(PlaceTool.spec(), place_tool.invoke)
    registry.register(RouteTool.spec(), route_tool.invoke)

    places = await registry.invoke(
        context,
        "search_places",
        {"keyword": "洪崖洞", "city": "重庆", "limit": 1},
    )
    route = await registry.invoke(
        context,
        "get_route",
        {
            "origin": {
                "longitude": 106.58,
                "latitude": 29.56,
                "coordinate_system": "GCJ-02",
            },
            "destination": {
                "longitude": 106.59,
                "latitude": 29.57,
                "coordinate_system": "GCJ-02",
            },
            "mode": "walking",
        },
    )

    assert places.results[0].name == "洪崖洞民俗风貌区"
    assert isinstance(route, RouteToolOutput)
    assert route.distance_m > 0
    assert runner.call_count == 2
