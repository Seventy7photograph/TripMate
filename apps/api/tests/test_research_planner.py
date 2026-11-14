# 文件说明：后端自动化测试：test_research_planner。
from app.agents.research_planner import LlmResearchPlanner
from app.providers.llm.base import (
    LlmUsage,
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
)
from app.schemas.ai import TripBriefContract


class ScriptedToolProvider:
    provider_name = "scripted"
    model_name = "tool-model"

    def __init__(self, calls: list[ToolCall]) -> None:
        self._calls = calls
        self.requests: list[ToolCallingRequest] = []

    async def generate_with_tools(
        self,
        request: ToolCallingRequest,
    ) -> ToolCallingResponse:
        self.requests.append(request)
        return ToolCallingResponse(
            content=None,
            tool_calls=self._calls,
            usage=LlmUsage(
                input_tokens=11,
                output_tokens=5,
                latency_ms=7,
                model_name=self.model_name,
            ),
        )


def brief() -> TripBriefContract:
    return TripBriefContract.model_validate(
        {
            "destination": "重庆",
            "origin": "上海",
            "start_date": "2026-12-01",
            "end_date": "2026-12-03",
            "party_size": 2,
            "budget_minor": 500_000,
            "currency": "CNY",
            "must_visit": ["洪崖洞"],
        }
    )


async def test_llm_research_planner_accepts_allowlisted_search_calls() -> None:
    provider = ScriptedToolProvider(
        [
            ToolCall(
                id="call-1",
                name="search_places",
                arguments={
                    "keyword": "洪崖洞",
                    "city": "重庆",
                    "limit": 3,
                },
            )
        ]
    )
    planner = LlmResearchPlanner(provider)

    result = await planner.plan(brief=brief(), tools=[])

    assert result.queries[0].keyword == "洪崖洞"
    assert result.queries[0].city == "重庆"
    assert result.input_tokens == 11
    assert provider.requests[0].tools
    assert provider.requests[0].metadata["prompt_agent"] == "research-planner"
    assert provider.requests[0].metadata["prompt_version"] == "1.0.0"
    assert result.prompt_versions[0]["prompt_id"] == "tool-selection"


async def test_llm_research_planner_rejects_unknown_tool() -> None:
    provider = ScriptedToolProvider(
        [
            ToolCall(
                id="call-1",
                name="arbitrary_url_fetch",
                arguments={"url": "https://example.com"},
            )
        ]
    )
    planner = LlmResearchPlanner(provider)

    result = await planner.plan(brief=brief(), tools=[])

    assert result.queries == []
