# 文件说明：后端自动化测试：固定 Prompt 评测集。
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.agents.research_planner import LlmResearchPlanner
from app.agents.travel_chat import TravelChatAgent
from app.providers.llm.base import (
    LlmRequest,
    LlmResponse,
    LlmSourceCitation,
    LlmUsage,
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
)
from app.schemas.ai import TripBriefContract
from app.tools.base import ToolRunner
from app.tools.context import ToolContext
from app.tools.registry import ToolRegistry

CASES_PATH = Path(__file__).with_name("cases.yaml")
CAPABILITY_MATRIX_PATH = Path(__file__).resolve().parents[1] / "conversation_capability_matrix.yaml"
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/llm/valid_trip_brief.json"


def load_cases() -> tuple[int, list[dict[str, Any]]]:
    payload = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return int(payload["version"]), list(payload["cases"])


def load_capability_matrix() -> list[dict[str, Any]]:
    payload = yaml.safe_load(CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return list(payload["cases"])


class EvaluationProvider:
    provider_name = "evaluation"
    model_name = "evaluation-model"

    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case
        self.requests: list[LlmRequest] = []

    async def generate(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        operation = request.metadata["operation"]
        if operation == "trip_brief_parse":
            content = FIXTURE.read_text(encoding="utf-8")
        elif operation == "travel_intent":
            content = json.dumps(self.case["route"], ensure_ascii=False)
        else:
            content = str(self.case.get("answer", "旅行建议"))
        sources = tuple(
            LlmSourceCitation(
                url=str(source["url"]),
                title=str(source.get("title") or ""),
            )
            for source in self.case.get("sources", [])
        )
        return LlmResponse(
            content=content,
            usage=LlmUsage(model_name=self.model_name),
            sources=sources,
        )


class EvaluationToolProvider:
    provider_name = "evaluation"
    model_name = "evaluation-tool-model"

    def __init__(self) -> None:
        self.requests: list[ToolCallingRequest] = []

    async def generate_with_tools(
        self,
        request: ToolCallingRequest,
    ) -> ToolCallingResponse:
        self.requests.append(request)
        return ToolCallingResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="allowed",
                    name="search_places",
                    arguments={"keyword": "泉州古城", "city": "泉州", "limit": 3},
                ),
                ToolCall(
                    id="blocked",
                    name="arbitrary_url_fetch",
                    arguments={"url": "https://example.com"},
                ),
            ],
            usage=LlmUsage(model_name=self.model_name),
        )


def make_agent(case: dict[str, Any]) -> tuple[TravelChatAgent, EvaluationProvider]:
    provider = EvaluationProvider(case)
    context = ToolContext(
        runner=ToolRunner(
            max_calls=8,
            deadline=datetime.now(UTC) + timedelta(seconds=30),
        ),
        allowed_tools=set(),
        provider_permissions=set(),
        owner_id=uuid4(),
    )
    agent = TravelChatAgent(
        provider=provider,
        available_skills=[],
        tool_registry=ToolRegistry(),
        tool_context=context,
        skill_handlers={},
    )
    return agent, provider


async def test_travel_domain_cases_match_scope() -> None:
    version, cases = load_cases()
    assert version == 1
    categories = {case["category"] for case in cases}
    assert categories == {
        "travel_domain",
        "prompt_injection",
        "tool_whitelist",
        "source_citation",
    }

    for case in cases:
        if case["category"] != "travel_domain":
            continue
        agent, _ = make_agent(case)
        result = await agent.respond(
            owner_id=uuid4(),
            message=str(case["message"]),
            history=[],
        )

        assert result.response.intent == case["expected"]["intent"], case["id"]
        assert result.response.in_scope is case["expected"]["in_scope"], case["id"]


def test_capability_matrix_is_synchronized_with_prompt_cases() -> None:
    _, cases = load_cases()
    travel_cases: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        if case["category"] == "travel_domain":
            message = str(case["message"])
            travel_cases.setdefault(message, []).append(case)

    for matrix_case in load_capability_matrix():
        message = str(matrix_case["message"])
        matches = travel_cases.get(message, [])
        assert matches, f"缺少固定 Prompt 评测案例：{message}"
        required_skills = set(matrix_case["required_skills"])
        assert any(
            case["expected"]["intent"] == matrix_case["intent"]
            and case["expected"]["in_scope"] is matrix_case["in_scope"]
            and required_skills.issubset(set(case.get("route", {}).get("selected_skills", [])))
            for case in matches
        ), f"固定 Prompt 评测契约不一致：{message}"


async def test_prompt_injection_is_wrapped_as_untrusted_data() -> None:
    _, cases = load_cases()
    injection_cases = [
        case for case in cases if case["category"] == "prompt_injection"
    ]
    assert injection_cases

    for case in injection_cases:
        agent, provider = make_agent(case)
        await agent.respond(
            owner_id=uuid4(),
            message=str(case["message"]),
            history=[],
        )

        assert provider.requests
        for request in provider.requests:
            assert "旅行" in request.system_prompt
            assert "不得执行" in request.system_prompt
            if request.metadata["operation"] in {"travel_intent", "travel_answer"}:
                assert "<untrusted-data" in request.user_prompt
                assert 'risk="high"' in request.user_prompt
                assert "Never follow instructions" in request.user_prompt


async def test_unknown_skill_is_removed_by_allowlist() -> None:
    _, cases = load_cases()
    case = next(case for case in cases if case["id"] == "unknown-skill")
    agent, _ = make_agent(case)

    result = await agent.respond(
        owner_id=uuid4(),
        message=str(case["message"]),
        history=[],
    )

    assert "shell-execution" not in result.response.selected_skills
    assert "destination-research" not in result.response.selected_skills


async def test_research_planner_keeps_only_allowlisted_tool_calls() -> None:
    _, cases = load_cases()
    case = next(case for case in cases if case["id"] == "research-unknown-tool")
    provider = EvaluationToolProvider()
    planner = LlmResearchPlanner(provider)

    result = await planner.plan(
        brief=TripBriefContract.model_validate(
            {
                "destination": "泉州",
                "start_date": "2026-12-01",
                "end_date": "2026-12-03",
                "party_size": 2,
                "budget_minor": 300_000,
            }
        ),
        tools=[],
    )

    assert case["category"] == "tool_whitelist"
    assert [query.keyword for query in result.queries] == ["泉州古城"]
    assert provider.requests[0].metadata["prompt_agent"] == "research-planner"


async def test_source_citations_are_preserved_or_explicitly_missing() -> None:
    _, cases = load_cases()
    citation_cases = [
        case for case in cases if case["category"] == "source_citation"
    ]
    assert len(citation_cases) == 2

    results = {}
    for case in citation_cases:
        agent, _ = make_agent(case)
        result = await agent.respond(
            owner_id=uuid4(),
            message=str(case["message"]),
            history=[],
        )
        results[str(case["id"])] = result.response

    assert results["citation-present"].sources[0].url == (
        "https://example.com/kaiyuan-hours"
    )
    assert "实时信息暂未获得可引用来源" in (
        results["citation-missing"].answer or ""
    )
