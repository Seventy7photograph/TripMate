# 文件说明：后端自动化测试：test_travel_graph。
import asyncio
import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.itinerary_composer import (
    LlmItineraryComposer,
    MockItineraryComposer,
    RetryableCompositionError,
)
from app.agents.research_planner import MockResearchPlanner, ResearchPlanResult
from app.graph.travel_graph import GraphLimits, TravelGraph
from app.providers.base import PlaceQuery, ProviderError, place_to_record
from app.providers.llm.base import (
    LlmProviderError,
    LlmRequest,
    LlmResponse,
    LlmTimeoutError,
    LlmUsage,
)
from app.providers.mock_map import MockMapProvider
from app.schemas.ai import TripBriefContract

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def brief_fixture() -> TripBriefContract:
    payload = json.loads(
        (FIXTURES / "trip_briefs/chongqing-full.json").read_text(encoding="utf-8")
    )
    return TripBriefContract.model_validate(payload)


class FailingComposer:
    provider_name = "test"
    model_name = "failing-composer"

    def __init__(self) -> None:
        self.calls = 0

    async def compose(self, **_: object):
        from app.agents.itinerary_composer import RetryableCompositionError

        self.calls += 1
        raise RetryableCompositionError("no_valid_stops")


class SlowComposer(FailingComposer):
    async def compose(self, **_: object):
        self.calls += 1
        await asyncio.sleep(1)
        raise AssertionError("timeout should cancel this composer")


class ProviderFailureComposer:
    provider_name = "test"
    model_name = "provider-failure"

    async def compose(self, **_: object):
        raise LlmProviderError(
            "LLM provider rejected the request (HTTP 400): invalid_request_error"
        )


class ScriptedLlmProvider:
    provider_name = "scripted"
    model_name = "scripted-model"

    def __init__(self, content: str) -> None:
        self._content = content
        self.requests: list[LlmRequest] = []

    async def generate(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        return LlmResponse(
            content=self._content,
            usage=LlmUsage(
                input_tokens=20,
                output_tokens=30,
                latency_ms=40,
                model_name="scripted-model-2026",
            ),
        )


class FailingMapProvider(MockMapProvider):
    async def search_places(self, query: PlaceQuery):
        del query
        raise ProviderError("upstream unavailable")


class PartiallyFailingMapProvider(MockMapProvider):
    async def search_places(self, query: PlaceQuery):
        if query.keyword == "失败地点":
            raise ProviderError("upstream unavailable")
        return await super().search_places(query)


class TimeoutResearchPlanner:
    provider_name = "test"
    model_name = "timeout-research"

    async def plan(self, **_: object):
        raise LlmTimeoutError("tool choice timed out")


class CountingComposer:
    provider_name = "test"
    model_name = "counting-composer"

    def __init__(self) -> None:
        self.calls = 0
        self._delegate = MockItineraryComposer()

    async def compose(self, **kwargs: object):
        self.calls += 1
        return await self._delegate.compose(**kwargs)


class PromptedResearchPlanner(MockResearchPlanner):
    async def plan(self, **kwargs: object) -> ResearchPlanResult:
        result = await super().plan(**kwargs)
        return ResearchPlanResult(
            queries=result.queries,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model_name=result.model_name,
            provider_name=result.provider_name,
            prompt_versions=[
                {
                    "agent": "research-planner",
                    "prompt_id": "tool-selection",
                    "version": "1.0.0",
                    "sha256": "research-digest",
                }
            ],
        )


class PromptedComposer(MockItineraryComposer):
    async def compose(self, **kwargs: object):
        from app.agents.itinerary_composer import ComposerResult

        result = await super().compose(**kwargs)
        return ComposerResult(
            draft=result.draft,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            model_name=result.model_name,
            provider_name=result.provider_name,
            prompt_versions=[
                {
                    "agent": "itinerary-composer",
                    "prompt_id": "system",
                    "version": "1.0.0",
                    "sha256": "composer-digest",
                }
            ],
        )


async def test_travel_graph_generates_candidate_backed_itinerary() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        limits=GraphLimits(
            max_loops=2,
            max_tool_calls=12,
            timeout_seconds=10,
            max_cost_minor=1_000,
        ),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "completed"
    assert outcome.draft is not None
    assert len(outcome.draft.days) == 3
    assert outcome.draft.days[0].date.isoformat() == "2026-12-01"
    assert outcome.state["loop_count"] == 0
    assert 0 < outcome.state["tool_call_count"] <= 12
    candidate_ids = {
        item["provider_place_id"] for item in outcome.state["candidates"]
    }
    stopped_ids = {
        stop.place_id for day in outcome.draft.days for stop in day.stops
    }
    assert stopped_ids <= candidate_ids
    assert outcome.tool_audits
    assert all(audit.input_hash for audit in outcome.tool_audits)
    assert [event.type for event in outcome.events][0] == "stage"
    assert outcome.events[-1].type == "complete"
    assert any(event.type == "tool_call" for event in outcome.events)
    assert any(event.type == "validation" for event in outcome.events)
    assert outcome.draft.days[0].evidence_ids
    assert outcome.draft.days[0].daily_summary
    assert any(
        event.stage == "evidence_plan_complete"
        for event in outcome.events
    )
    assert any(
        event.stage == "evidence_verify"
        for event in outcome.events
    )


async def test_travel_graph_writes_langgraph_checkpoint() -> None:
    checkpointer = InMemorySaver()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
        thread_id="planning-run-1",
        checkpointer=checkpointer,
    )

    assert outcome.status == "completed"
    checkpoint = await checkpointer.aget_tuple(
        {"configurable": {"thread_id": "planning-run-1"}}
    )
    assert checkpoint is not None


async def test_travel_graph_merges_prompt_usage_from_agents() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=PromptedComposer(),
        research_planner=PromptedResearchPlanner(),
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "completed"
    assert outcome.prompt_versions == [
        {
            "agent": "research-planner",
            "prompt_id": "tool-selection",
            "version": "1.0.0",
            "sha256": "research-digest",
        },
        {
            "agent": "itinerary-composer",
            "prompt_id": "system",
            "version": "1.0.0",
            "sha256": "composer-digest",
        },
    ]


async def test_travel_graph_resumes_without_recomposing() -> None:
    checkpointer = InMemorySaver()
    composer = CountingComposer()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=composer,
        limits=GraphLimits(),
    )
    kwargs = {
        "trip_id": "trip-1",
        "version": 1,
        "brief": brief_fixture(),
        "brief_confirmed": True,
        "thread_id": "resume-run-1",
        "checkpointer": checkpointer,
    }

    first = await graph.run(**kwargs)
    second = await graph.run(**kwargs, resume=True)

    assert first.status == "completed"
    assert second.status == "completed"
    assert composer.calls == 1
    assert second.events[-1].type == "complete"


async def test_unconfirmed_brief_does_not_start_generation() -> None:
    composer = FailingComposer()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=composer,
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=False,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "brief_not_confirmed"
    assert outcome.state["tool_call_count"] == 0
    assert composer.calls == 0
    assert outcome.events[-1].type == "error"


async def test_provider_failure_fails_with_explicit_error() -> None:
    graph = TravelGraph(
        map_provider=FailingMapProvider(),
        composer=None,
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "provider_error"
    assert outcome.draft is None
    assert outcome.tool_audits[0].status == "error"


async def test_composer_provider_error_is_propagated_to_events() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=ProviderFailureComposer(),  # type: ignore[arg-type]
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        brief_confirmed=True,
    )

    assert outcome.status == "failed"
    assert outcome.error_code == "llm_provider_error"
    assert outcome.error_message is not None
    assert "HTTP 400" in outcome.error_message
    assert "invalid_request_error" in outcome.error_message
    assert any(
        event.type == "error"
        and event.message is not None
        and "HTTP 400" in event.message
        for event in outcome.events
    )


async def test_research_continues_when_one_query_fails() -> None:
    brief = brief_fixture().model_copy(update={"must_visit": ["失败地点"]})
    graph = TravelGraph(
        map_provider=PartiallyFailingMapProvider(),
        composer=None,
        limits=GraphLimits(),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief,
        brief_confirmed=True,
    )

    assert outcome.status == "completed"
    assert outcome.state["candidates"]
    assert any(
        audit.status == "error" for audit in outcome.tool_audits
    )


async def test_research_llm_timeout_fails_with_graph_timeout() -> None:
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=None,
        research_planner=TimeoutResearchPlanner(),
        limits=GraphLimits(),
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


async def test_llm_composer_uses_only_candidate_backed_places() -> None:
    places = await MockMapProvider().search_places(
        PlaceQuery(keyword="重庆 景点", city="重庆", limit=3)
    )
    candidates = [place_to_record(place) for place in places]
    content = json.dumps(
        {
            "days": [
                {
                    "date": "2026-12-01",
                    "theme": "城市初见",
                    "stops": [
                        {
                            "place_id": candidates[0]["provider_place_id"],
                            "start_time": "09:00",
                            "duration_minutes": 90,
                            "estimated_cost_minor": 5_000,
                        }
                    ],
                }
            ]
        },
        ensure_ascii=False,
    )
    provider = ScriptedLlmProvider(content)
    composer = LlmItineraryComposer(provider)

    result = await composer.compose(
        trip_id="trip-1",
        version=1,
        brief=brief_fixture(),
        candidates=candidates,
    )

    assert result.draft.days[0].stops[0].place_id == candidates[0]["provider_place_id"]
    assert result.draft.days[0].stops[0].source.provider == "mock"
    assert result.input_tokens == 20
    assert result.output_tokens == 30
    assert result.provider_name == "scripted"
    assert provider.requests[0].metadata["operation"] == "itinerary_compose"
    assert provider.requests[0].metadata["prompt_agent"] == "itinerary-composer"
    assert provider.requests[0].metadata["prompt_version"] == "1.0.0"
    assert result.prompt_versions[0]["prompt_id"] == "system"
    assert '"days"' in provider.requests[0].user_prompt
    assert provider.requests[0].max_tokens == 24_000


async def test_llm_composer_rejects_unknown_place_id() -> None:
    places = await MockMapProvider().search_places(
        PlaceQuery(keyword="重庆 景点", city="重庆", limit=1)
    )
    candidates = [place_to_record(place) for place in places]
    composer = LlmItineraryComposer(
        ScriptedLlmProvider(
            json.dumps(
                {
                    "days": [
                        {
                            "date": "2026-12-01",
                            "stops": [
                                {
                                    "place_id": "invented-place",
                                    "start_time": "09:00",
                                    "duration_minutes": 60,
                                    "estimated_cost_minor": 0,
                                }
                            ],
                        }
                    ]
                }
            )
        )
    )

    with pytest.raises(RetryableCompositionError, match="unknown_place"):
        await composer.compose(
            trip_id="trip-1",
            version=1,
            brief=brief_fixture(),
            candidates=candidates,
        )
