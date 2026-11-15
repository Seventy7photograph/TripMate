# 文件说明：Agent Skill 功能开关与单主 Agent 回退测试。

import json
from pathlib import Path
from uuid import UUID

import pytest

from app.core.config import get_settings
from app.graph.travel_graph import GraphLimits, TravelGraph
from app.main import app
from app.providers.mock_map import MockMapProvider
from app.schemas.ai import TripBriefContract
from app.services.feature_service import (
    FEATURE_DEFINITIONS,
    FeatureDisabledError,
    FeatureFlagService,
)
from app.skills.runtime import build_skill_runtime
from tests.test_auth import register_user

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def brief_fixture() -> TripBriefContract:
    return TripBriefContract.model_validate(
        json.loads(
            (
                FIXTURES / "trip_briefs/chongqing-full.json"
            ).read_text(encoding="utf-8")
        )
    )


class ExplodingRouter:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, **_: object) -> object:
        self.calls += 1
        raise AssertionError("router must not run when rollout is disabled")


def test_skill_rollout_feature_flags_are_registered() -> None:
    assert {
        "agent_skills_enabled",
        "agent_skill_router_enabled",
        "mcp_gateway_enabled",
    } <= set(FEATURE_DEFINITIONS)


@pytest.mark.parametrize(
    ("skills_enabled", "router_enabled", "expected_reason"),
    [
        (False, True, "agent_skills_disabled"),
        (True, False, "agent_skill_router_disabled"),
    ],
)
async def test_disabled_skill_rollout_falls_back_to_single_agent_flow(
    skills_enabled: bool,
    router_enabled: bool,
    expected_reason: str,
) -> None:
    router = ExplodingRouter()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        skill_router=router,  # type: ignore[arg-type]
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
        skills_enabled=skills_enabled,
        router_enabled=router_enabled,
    )

    assert outcome.status == "completed"
    assert router.calls == 0
    assert outcome.skill_route is not None
    assert outcome.skill_route["fallback_reason"] == expected_reason
    assert outcome.skill_route["selected_skills"] == []
    assert outcome.skills_used == []


async def test_weather_provider_flag_blocks_weather_and_altitude_tools(
    api_client,
) -> None:
    registration = await register_user(api_client)
    owner_id = UUID(str(registration["user"]["id"]))
    await FeatureFlagService(app.state.test_session).toggle(
        key="weather_provider",
        enabled=False,
        actor_id=owner_id,
        reason="weather rollout disabled",
    )
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=owner_id,
    )

    with pytest.raises(FeatureDisabledError):
        await runtime.execute(
            "weather-and-clothing",
            {"city": "重庆", "date": "2026-12-01"},
        )
