# 文件说明：后端自动化测试：test_control_tools。
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.providers.base import GeoPoint, RouteRequest, RouteResult
from app.providers.mock_map import MockMapProvider
from app.tools.base import ToolRunner
from app.tools.budget_tools import BudgetTool, BudgetToolInput
from app.tools.context import ToolContext
from app.tools.route_tools import RouteTool, RouteToolInput


class CountingMapProvider(MockMapProvider):
    def __init__(self) -> None:
        self.route_calls = 0

    async def get_route(self, request: RouteRequest) -> RouteResult:
        self.route_calls += 1
        return await super().get_route(request)


async def test_route_tool_reuses_identical_requests() -> None:
    provider = CountingMapProvider()
    runner = ToolRunner(
        max_calls=12,
        deadline=datetime.now(UTC) + timedelta(minutes=1),
    )
    tool = RouteTool(
        provider,
        ToolContext(
            runner=runner,
            allowed_tools={"get_route"},
            provider_permissions={"map"},
            owner_id=uuid4(),
        ),
    )
    request = RouteToolInput(
        origin=GeoPoint(106.58, 29.56),
        destination=GeoPoint(106.59, 29.57),
        mode="walking",
    )

    first = await tool.get(request)
    second = await tool.get(request)

    assert first == second
    assert provider.route_calls == 1
    assert runner.call_count == 1


async def test_budget_tool_reuses_identical_requests() -> None:
    runner = ToolRunner(
        max_calls=12,
        deadline=datetime.now(UTC) + timedelta(minutes=1),
    )
    tool = BudgetTool(
        ToolContext(
            runner=runner,
            allowed_tools={"calculate_budget"},
            provider_permissions={"deterministic"},
            owner_id=uuid4(),
        )
    )
    request = BudgetToolInput(
        stop_costs_minor=[10_000, 20_000],
        budget_minor=50_000,
    )

    first = await tool.calculate(request)
    second = await tool.calculate(request)

    assert first == second
    assert runner.call_count == 1
