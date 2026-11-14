# 文件说明：后端自动化测试：Graph Skill Router 回退。
import json
from pathlib import Path

from app.graph.travel_graph import GraphLimits, TravelGraph
from app.providers.mock_map import MockMapProvider
from app.schemas.ai import TripBriefContract
from app.skills.router import SkillRouteDecision

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def brief_fixture() -> TripBriefContract:
    return TripBriefContract.model_validate(
        json.loads(
            (
                FIXTURES / "trip_briefs/chongqing-full.json"
            ).read_text(encoding="utf-8")
        )
    )


class FailingRouter:
    def route(self, **_: object) -> SkillRouteDecision:
        raise RuntimeError("router unavailable")


class ClarifyingRouter:
    def route(self, **_: object) -> SkillRouteDecision:
        return SkillRouteDecision(
            intent="clarify",
            confidence=0.35,
            selected_skills=[],
            needed_clarifications=["请补充具体目的地和日期。"],
            budget={
                "max_tool_calls": 0,
                "max_tokens": 1200,
                "allowed_tools": [],
                "allowed_mcp_connectors": [],
            },
            requires_confirmation=False,
        )


async def test_router_failure_falls_back_to_existing_graph() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        skill_router=FailingRouter(),  # type: ignore[arg-type]
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "completed"
    assert outcome.skill_route is not None
    assert outcome.skill_route["fallback_reason"] == "router unavailable"
    assert any(
        event.message and "回退" in event.message
        for event in outcome.events
    )


async def test_low_confidence_route_stops_before_research() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        skill_router=ClarifyingRouter(),  # type: ignore[arg-type]
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "clarification_required"
    assert outcome.draft is None
    assert not outcome.state.get("candidates")
