# 文件说明：后端自动化测试：test_agent_budget_limits。
import asyncio
import json
from pathlib import Path

from app.agents.itinerary_composer import (
    ComposerResult,
    MockItineraryComposer,
    RetryableCompositionError,
)
from app.graph.travel_graph import GraphLimits, TravelGraph
from app.providers.mock_map import MockMapProvider
from app.schemas.ai import TripBriefContract

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def brief_fixture() -> TripBriefContract:
    payload = json.loads(
        (FIXTURES / "trip_briefs/chongqing-full.json").read_text(encoding="utf-8")
    )
    return TripBriefContract.model_validate(payload)


class AlwaysRetryComposer:
    provider_name = "test"
    model_name = "always-retry"

    def __init__(self) -> None:
        self.calls = 0

    async def compose(self, **_: object):
        self.calls += 1
        raise RetryableCompositionError("invalid_candidate")


class ExpensiveComposer(MockItineraryComposer):
    async def compose(self, **kwargs: object) -> ComposerResult:
        result = await super().compose(**kwargs)
        return ComposerResult(
            draft=result.draft,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model_name=result.model_name,
            provider_name=result.provider_name,
            estimated_cost_minor=101,
        )


class SlowComposer:
    provider_name = "test"
    model_name = "slow"

    async def compose(self, **_: object):
        await asyncio.sleep(1)
        raise AssertionError("timeout should cancel this composer")


async def test_tool_call_limit_fails_closed() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=MockItineraryComposer(),
        limits=GraphLimits(max_tool_calls=1, timeout_seconds=10),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "tool_limit_exceeded"
    assert outcome.state["tool_call_count"] == 1
    assert outcome.draft is None


async def test_tool_limit_during_route_checks_fails_closed() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=MockItineraryComposer(),
        limits=GraphLimits(max_tool_calls=2, timeout_seconds=10),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "tool_limit_exceeded"
    assert outcome.state["tool_call_count"] == 2
    assert outcome.draft is None


async def test_replan_loop_stops_after_two_repairs() -> None:
    composer = AlwaysRetryComposer()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=composer,
        limits=GraphLimits(max_loops=2, max_tool_calls=12, timeout_seconds=10),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "max_loops_exceeded"
    assert outcome.state["loop_count"] == 2
    assert composer.calls == 3
    assert outcome.draft is None


async def test_graph_timeout_fails_closed() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=SlowComposer(),
        limits=GraphLimits(max_tool_calls=12, timeout_seconds=0.05),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "graph_timeout"
    assert outcome.draft is None


async def test_cost_limit_fails_before_persisting_draft() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=ExpensiveComposer(),
        limits=GraphLimits(
            max_tool_calls=12,
            timeout_seconds=10,
            max_cost_minor=100,
        ),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "cost_limit_exceeded"
    assert outcome.state["estimated_cost_minor"] == 101
    assert outcome.draft is None
