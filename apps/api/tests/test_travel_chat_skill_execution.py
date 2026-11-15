# 文件说明：后端自动化测试：旅行问答必须执行路由选择的 Skill。
import json
from uuid import uuid4

import httpx

from app.agents.travel_chat import TravelChatAgent
from app.core.config import get_settings
from app.main import app
from app.providers.llm.base import LlmRequest, LlmResponse, LlmUsage
from app.skills.runtime import build_skill_runtime


class BudgetQuestionProvider:
    provider_name = "scripted-live-contract"
    model_name = "deepseek-flash"

    def __init__(self) -> None:
        self.requests: list[LlmRequest] = []

    async def generate(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        if request.metadata.get("operation") == "travel_intent":
            content = json.dumps(
                {
                    "intent": "budget_advice",
                    "in_scope": True,
                    "confidence": 0.96,
                    "selected_skills": ["budget-optimization"],
                    "skill_calls": [
                        {
                            "name": "budget-optimization",
                            "arguments": {
                                "stop_costs_minor": [10_000, 20_000],
                                "budget_minor": 50_000,
                            },
                        }
                    ],
                }
            )
        else:
            content = "当前已知费用为 300 元，预算上限为 500 元。"
        return LlmResponse(
            content=content,
            usage=LlmUsage(model_name=self.model_name),
        )


class LowConfidenceSocialProvider:
    provider_name = "scripted-low-confidence"
    model_name = "deepseek-flash"

    async def generate(self, request: LlmRequest) -> LlmResponse:
        if request.metadata.get("operation") == "travel_intent":
            content = json.dumps(
                {
                    "intent": "clarify",
                    "in_scope": True,
                    "confidence": 0.35,
                    "selected_skills": [],
                }
            )
        else:
            content = json.dumps(
                {
                    "destination": "泉州",
                    "interests": ["人文"],
                }
            )
        return LlmResponse(
            content=content,
            usage=LlmUsage(model_name=self.model_name),
        )


async def test_budget_question_executes_selected_skill(
    api_client: httpx.AsyncClient,
) -> None:
    settings = get_settings()
    owner_id = uuid4()
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=settings,
        owner_id=owner_id,
    )
    provider = BudgetQuestionProvider()
    agent = TravelChatAgent(
        provider=provider,
        available_skills=runtime.registry.latest_manifests(),
        tool_registry=runtime.tools,
        tool_context=runtime.tool_context,
        skill_handlers=runtime.handlers,
    )

    result = await agent.respond(
        owner_id=owner_id,
        message="泉州三天预算500元够吗",
        history=[],
    )

    assert result.response.intent == "budget_advice"
    assert "calculate_budget" in result.response.used_tools
    assert result.skills_used == [
        {
            "name": "trip-intent-routing",
            "version": "1.0.0",
            "status": "completed",
        },
        {
            "name": "budget-optimization",
            "version": "1.0.0",
            "status": "completed",
        }
    ]
    assert "300 元" in (result.response.answer or "")
    assert '"input_schema"' in provider.requests[0].user_prompt


async def test_routing_skill_recovers_low_confidence_model_decision(
    api_client: httpx.AsyncClient,
) -> None:
    settings = get_settings()
    owner_id = uuid4()
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=settings,
        owner_id=owner_id,
    )
    agent = TravelChatAgent(
        provider=LowConfidenceSocialProvider(),
        available_skills=runtime.registry.latest_manifests(),
        tool_registry=runtime.tools,
        tool_context=runtime.tool_context,
        skill_handlers=runtime.handlers,
    )

    result = await agent.respond(
        owner_id=owner_id,
        message="帮我写一段泉州旅行朋友圈文案",
        history=[],
    )

    assert result.response.intent == "travel_question"
    assert "social-copywriting" in result.response.selected_skills
    assert {
        item["name"] for item in result.skills_used
    } >= {"trip-intent-routing", "social-copywriting"}
