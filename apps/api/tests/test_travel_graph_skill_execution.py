# 文件说明：后端自动化测试：规划 Graph 必须执行 Router 选中的 Skill。
import json
from pathlib import Path
from uuid import uuid4

import httpx

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
        available_skills=runtime.registry.latest_manifests(),
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
        available_skills=runtime.registry.latest_manifests(),
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
