# 文件说明：后端自动化测试：test_prompt_runtime_usage。
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.agents.requirement_parser import RequirementParser
from app.agents.travel_chat import TravelChatAgent
from app.prompts.registry import (
    TRAVEL_CHAT_INTENT_ROUTER,
    load_prompt,
)
from app.providers.llm.base import (
    LlmRequest,
    LlmResponse,
    LlmSourceCitation,
    LlmUsage,
)
from app.tools.base import ToolRunner
from app.tools.context import ToolContext
from app.tools.registry import ToolRegistry

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "llm"
    / "valid_trip_brief.json"
)


class RecordingProvider:
    provider_name = "recording"
    model_name = "recording-model"

    def __init__(self) -> None:
        self.request: LlmRequest | None = None

    async def generate(self, request: LlmRequest) -> LlmResponse:
        self.request = request
        return LlmResponse(
            content=FIXTURE.read_text(encoding="utf-8"),
            usage=LlmUsage(model_name=self.model_name),
        )


async def test_requirement_parser_records_exact_prompt_version() -> None:
    provider = RecordingProvider()

    result = await RequirementParser(provider).parse(
        "2026年12月1日到12月3日，2个人从上海去重庆，预算5000元。"
    )

    assert provider.request is not None
    assert provider.request.metadata["prompt_agent"] == "requirement-parser"
    assert provider.request.metadata["prompt_id"] == "system"
    assert provider.request.metadata["prompt_version"] == "1.1.0"
    assert len(provider.request.metadata["prompt_sha256"]) == 64
    assert result.prompt_versions == [
        {
            "agent": "requirement-parser",
            "prompt_id": "system",
                "version": "1.1.0",
            "sha256": provider.request.metadata["prompt_sha256"],
        }
    ]


class TwoStepTravelProvider:
    provider_name = "scripted"
    model_name = "scripted-travel"

    def __init__(self) -> None:
        self.requests: list[LlmRequest] = []

    async def generate(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        if request.metadata["operation"] == "travel_intent":
            return LlmResponse(
                content=json.dumps(
                    {
                        "intent": "destination_research",
                        "in_scope": True,
                        "confidence": 0.95,
                        "selected_skills": [],
                        "destination": "泉州",
                        "place_query": "开元寺",
                        "web_search": True,
                        "read_url": False,
                        "deep_research": False,
                    }
                ),
                usage=LlmUsage(model_name=self.model_name),
            )
        return LlmResponse(
            content="开放时间请以官方公告为准。",
            usage=LlmUsage(model_name=self.model_name),
            sources=(
                LlmSourceCitation(
                    url="https://example.com/quanzhou",
                    title="泉州文旅",
                ),
            ),
        )


async def test_travel_chat_records_both_prompt_versions() -> None:
    provider = TwoStepTravelProvider()
    context = ToolContext(
        runner=ToolRunner(
            max_calls=4,
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

    result = await agent.respond(
        owner_id=uuid4(),
        message="泉州开元寺开放时间？",
        history=[],
    )

    assert [request.metadata["prompt_id"] for request in provider.requests] == [
        "intent-router",
        "answer",
    ]
    assert result.prompt_versions == [
        prompt
        for request in provider.requests
        for prompt in [
            {
                "agent": request.metadata["prompt_agent"],
                "prompt_id": request.metadata["prompt_id"],
                "version": request.metadata["prompt_version"],
                "sha256": request.metadata["prompt_sha256"],
            }
        ]
    ]


def test_live_intent_prompt_requires_structured_skill_calls() -> None:
    prompt = load_prompt(TRAVEL_CHAT_INTENT_ROUTER)

    assert prompt.version == "1.3.0"
    assert '"skill_calls"' in prompt.content
    assert "arguments" in prompt.content
    assert "不得编造" in prompt.content
