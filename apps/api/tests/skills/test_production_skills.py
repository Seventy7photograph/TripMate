# 文件说明：后端自动化测试：test_production_skills。
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx

from app.evidence.models import EvidenceRecord
from app.main import app
from app.providers.mock_map import MockMapProvider
from app.skills.executor import SkillContext, SkillExecutor
from app.skills.production import (
    BudgetOptimizationInput,
    DestinationResearchInput,
    EvidenceVerificationInput,
    RouteOptimizationInput,
    SocialCopywritingInput,
    TravelMemoryInput,
    TripIntentRoutingInput,
    production_skill_handlers,
)
from app.skills.registry import SkillRegistry
from app.tools.base import ToolRunner
from app.tools.budget_tools import BudgetTool
from app.tools.context import ToolContext
from app.tools.memory_tools import MemoryTool
from app.tools.place_tools import PlaceTool
from app.tools.registry import ToolRegistry
from app.tools.route_tools import RouteTool
from tests.test_auth import auth_headers, register_user

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PROJECT_ROOT / "skills"


class StubMemoryService:
    async def authorized_items(
        self,
        *,
        owner_id: object,
        query: str,
        limit: int,
    ) -> list[object]:
        del owner_id, query, limit
        return [
            SimpleNamespace(
                id=uuid4(),
                category="lodging",
                content="住宿优先靠近地铁站",
                updated_at=datetime.now(UTC),
            )
        ]


def skill_runtime() -> tuple[
    SkillRegistry,
    ToolRegistry,
    ToolContext,
    SkillExecutor,
]:
    skills = SkillRegistry(
        known_tools={
            "search_places",
            "get_route",
            "calculate_budget",
            "get_authorized_memory_context",
            "get_weather",
            "search_nearby_places",
            "get_place_detail",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "extract_attachment",
        }
    )
    skills.load(SKILLS_ROOT)
    runner = ToolRunner(
        max_calls=12,
        deadline=datetime.now(UTC) + timedelta(seconds=30),
    )
    context = ToolContext(
        runner=runner,
        allowed_tools={
            "search_places",
            "get_route",
            "calculate_budget",
            "get_authorized_memory_context",
        },
        provider_permissions={"map", "deterministic", "memory"},
        owner_id=uuid4(),
    )
    tools = ToolRegistry()
    provider = MockMapProvider()
    place_tool = PlaceTool(provider, context)
    route_tool = RouteTool(provider, context)
    budget_tool = BudgetTool(context)
    memory_tool = MemoryTool(StubMemoryService(), context)  # type: ignore[arg-type]
    tools.register(PlaceTool.spec(), place_tool.invoke)
    tools.register(RouteTool.spec(), route_tool.invoke)
    tools.register(BudgetTool.spec(), budget_tool.invoke)
    tools.register(MemoryTool.spec(), memory_tool.invoke)
    return skills, tools, context, SkillExecutor()


async def test_destination_research_executes_place_tool() -> None:
    skills, tools, context, executor = skill_runtime()
    manifest = skills.get("destination-research")
    handlers = production_skill_handlers(tools, context)

    result = await executor.execute(
        manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[manifest.name],
        ),
        DestinationResearchInput(query="洪崖洞", city="重庆", limit=1),
    )

    assert result.output.places[0].name == "洪崖洞民俗风貌区"
    assert result.tool_calls == 1


async def test_route_and_budget_skills_execute_declared_tools() -> None:
    skills, tools, context, executor = skill_runtime()
    handlers = production_skill_handlers(tools, context)
    route_manifest = skills.get("route-optimization")
    route_result = await executor.execute(
        route_manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[route_manifest.name],
        ),
        RouteOptimizationInput(
            origin={
                "longitude": 106.58,
                "latitude": 29.56,
                "coordinate_system": "GCJ-02",
            },
            destination={
                "longitude": 106.59,
                "latitude": 29.57,
                "coordinate_system": "GCJ-02",
            },
            mode="walking",
        ),
    )
    budget_manifest = skills.get("budget-optimization")
    budget_result = await executor.execute(
        budget_manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[budget_manifest.name],
        ),
        BudgetOptimizationInput(
            stop_costs_minor=[10_000, 20_000],
            budget_minor=50_000,
        ),
    )

    assert route_result.output.distance_m > 0
    assert budget_result.output.estimated_minor == 30_000
    assert budget_result.output.within_budget is True


async def test_evidence_verification_marks_stale_record_without_tools() -> None:
    skills, tools, context, executor = skill_runtime()
    manifest = skills.get("evidence-verification")
    handlers = production_skill_handlers(tools, context)
    now = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
    record = EvidenceRecord(
        owner_id=context.owner_id or uuid4(),
        fact_type="weather",
        provider="amap-weather",
        fetched_at=now - timedelta(hours=2),
        valid_until=now - timedelta(hours=1),
        confidence=0.9,
        freshness="live",
        value={"temperature_c": 18},
    )

    result = await executor.execute(
        manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[manifest.name],
        ),
        EvidenceVerificationInput(records=[record], now=now),
    )

    assert result.tool_calls == 0
    assert [issue.code for issue in result.output.issues] == ["stale"]


async def test_contract_skills_route_memory_and_draft_copy() -> None:
    skills, tools, context, executor = skill_runtime()
    handlers = production_skill_handlers(tools, context)

    routing_manifest = skills.get("trip-intent-routing")
    routed = await executor.execute(
        routing_manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[routing_manifest.name],
        ),
        TripIntentRoutingInput(
            text="帮我写一段泉州旅行朋友圈文案",
            available_skills=["social-copywriting", "travel-memory"],
        ),
    )
    assert routed.output.intent == "social_copywriting"
    assert routed.output.selected_skills == ["social-copywriting"]

    memory_manifest = skills.get("travel-memory")
    memory = await executor.execute(
        memory_manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[memory_manifest.name],
        ),
        TravelMemoryInput(query="住宿偏好"),
    )
    assert memory.output.applied_count == 1
    assert "地铁站" in memory.output.items[0].content

    social_manifest = skills.get("social-copywriting")
    social = await executor.execute(
        social_manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[social_manifest.name],
        ),
        SocialCopywritingInput(
            destination="泉州",
            platform="wechat_moments",
            tone="quiet",
            confirmed_facts=["开元寺开放时间以现场公告为准"],
            trip_days=3,
        ),
    )
    assert social.output.title.startswith("泉州")
    assert social.output.warnings
    assert "未标注的信息" in social.output.body


async def test_router_skill_routes_attachment_to_bounded_tool() -> None:
    skills, tools, context, executor = skill_runtime()
    handlers = production_skill_handlers(tools, context)
    manifest = skills.get("trip-intent-routing")

    result = await executor.execute(
        manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[manifest.name],
        ),
        TripIntentRoutingInput(
            text="按附件截图整理这次旅行需求",
            available_skills=["attachment-understanding", "travel-memory"],
        ),
    )

    assert result.output.intent == "understand_attachment"
    assert result.output.selected_skills == ["attachment-understanding"]
    assert result.output.allowed_tools == ["extract_attachment"]


async def test_memory_tool_reads_only_enabled_authorized_rows(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    owner_id = UUID(str(registration["user"]["id"]))
    created = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(token),
        json={
            "category": "lodging",
            "content": "住宿优先靠近地铁站",
            "consent": True,
        },
    )
    assert created.status_code == 201, created.text
    from app.services.memory_service import MemoryService

    context = ToolContext(
        runner=ToolRunner(
            max_calls=2,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools={"get_authorized_memory_context"},
        provider_permissions={"memory"},
        owner_id=owner_id,
    )
    tools = ToolRegistry()
    memory_tool = MemoryTool(MemoryService(app.state.test_session), context)
    tools.register(MemoryTool.spec(), memory_tool.invoke)

    first = await tools.invoke(
        context,
        "get_authorized_memory_context",
        {"query": "住宿 地铁", "limit": 8},
    )
    assert first.applied_count == 1

    disabled = await api_client.patch(
        f"/api/v1/memories/{created.json()['id']}",
        headers=auth_headers(token),
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    second = await tools.invoke(
        context,
        "get_authorized_memory_context",
        {"query": "住宿 地铁", "limit": 8},
    )
    assert second.applied_count == 0
