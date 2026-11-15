# 文件说明：后端自动化测试：规划 Graph 必须执行 Router 选中的 Skill。
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.core.config import get_settings
from app.graph.travel_graph import GraphLimits, TravelGraph
from app.main import app
from app.providers.mock_map import MockMapProvider
from app.schemas.ai import TripBriefContract
from app.skills.runtime import build_skill_runtime

FIXTURES = Path(__file__).resolve().parent / "fixtures"


async def test_travel_graph_executes_selected_skills(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    settings = get_settings()
    owner_id = uuid4()
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=settings,
        owner_id=owner_id,
    )
    available_skills = runtime.registry.latest_manifests()
    runtime.selected_manifests = {
        skill.name: skill for skill in available_skills
    }
    brief = TripBriefContract.model_validate(
        json.loads(
            (FIXTURES / "trip_briefs/chongqing-full.json").read_text(
                encoding="utf-8"
            )
        )
    ).model_copy(
        update={
            "interests": ["城市漫步"],
            "lodging_preferences": [],
        }
    )
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        available_skills=available_skills,
        limits=GraphLimits(
            max_loops=2,
            max_tool_calls=12,
            timeout_seconds=10,
            max_cost_minor=1_000,
        ),
    )

    outcome = await graph.run(
        trip_id="trip-skill-runtime",
        version=1,
        brief=brief,
        brief_confirmed=True,
        owner_id=owner_id,
        available_skills=available_skills,
        skill_runtime=runtime,
    )

    used = {str(item["name"]) for item in outcome.skills_used}
    assert outcome.status == "completed"
    assert "destination-research" in used
    assert "route-optimization" in used
    assert "budget-optimization" in used
    assert "evidence-verification" in used
    assert {
        audit.tool_name for audit in runtime.tool_context.runner.audits
    } >= {"search_places", "get_route", "calculate_budget"}


async def test_travel_graph_uses_pinned_skill_manifest_version(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=uuid4(),
    )
    pinned = runtime.registry.get("destination-research").model_copy(
        update={"version": "0.9.0"}
    )
    runtime.selected_manifests = {"destination-research": pinned}
    brief = TripBriefContract.model_validate(
        json.loads(
            (FIXTURES / "trip_briefs/chongqing-full.json").read_text(
                encoding="utf-8"
            )
        )
    )
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        available_skills=[pinned],
        limits=GraphLimits(max_tool_calls=12, timeout_seconds=10),
    )

    outcome = await graph.run(
        trip_id="trip-pinned-skill",
        version=1,
        brief=brief,
        brief_confirmed=True,
        owner_id=runtime.tool_context.owner_id,
        available_skills=[pinned],
        skill_runtime=runtime,
    )

    destination = next(
        item
        for item in outcome.skills_used
        if item["name"] == "destination-research"
    )
    assert destination["version"] == "0.9.0"


async def test_evidence_verification_skill_respects_selected_state(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=uuid4(),
    )
    destination = runtime.registry.get("destination-research")
    runtime.selected_manifests = {"destination-research": destination}
    brief = TripBriefContract.model_validate(
        json.loads(
            (FIXTURES / "trip_briefs/chongqing-full.json").read_text(
                encoding="utf-8"
            )
        )
    )
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        available_skills=[destination],
        limits=GraphLimits(max_tool_calls=12, timeout_seconds=10),
    )

    outcome = await graph.run(
        trip_id="trip-disabled-evidence-skill",
        version=1,
        brief=brief,
        brief_confirmed=True,
        owner_id=runtime.tool_context.owner_id,
        available_skills=[destination],
        skill_runtime=runtime,
    )

    assert "evidence-verification" not in {
        str(item["name"]) for item in outcome.skills_used
    }


async def test_selected_manifest_lookup_fails_closed_when_disabled(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=uuid4(),
    )
    runtime.selected_manifests = {
        "destination-research": runtime.registry.get("destination-research")
    }

    with pytest.raises(LookupError):
        runtime.selected_manifest("evidence-verification")
