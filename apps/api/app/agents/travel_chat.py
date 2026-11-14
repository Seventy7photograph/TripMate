# 文件说明：AI Agent：travel_chat。
"""旅行对话路由，并按需接入可追溯的 Web 研究能力。"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.requirement_parser import RequirementParser
from app.prompts.catalog import prompt_request_metadata
from app.prompts.registry import (
    TRAVEL_CHAT_ANSWER,
    TRAVEL_CHAT_INTENT_ROUTER,
    load_prompt,
)
from app.providers.llm.base import (
    LlmProviderError,
    LlmRequest,
    LlmUsage,
    StructuredLlmProvider,
)
from app.schemas.chat import (
    ChatHistoryTurn,
    ChatSourceCitation,
    TravelChatResponse,
    TravelIntent,
)
from app.services.prompt_safety import PromptSafetyService
from app.skills.executor import SkillContext, SkillExecutor, SkillHandler
from app.skills.manifest import SkillManifest
from app.skills.production import (
    DestinationResearchInput,
    DestinationResearchOutput,
)
from app.tools.context import ToolContext
from app.tools.registry import ToolRegistry

_OUT_OF_SCOPE_ANSWER = (
    "这个问题可能不在我的旅行能力范围内。"
    "如果是出行相关的事，我可以继续帮你规划行程、研究目的地、比较路线、"
    "估算预算，或查询交通、住宿、天气和旅行安全信息。"
)
_GREETING_ANSWER = (
    "你好，我在。可以和我聊想去哪里、怎么安排，"
    "也可以问交通、住宿、预算或当地体验。"
)

_TRAVEL_TERMS = (
    "旅行",
    "旅游",
    "行程",
    "景点",
    "目的地",
    "酒店",
    "民宿",
    "住宿",
    "路线",
    "交通",
    "机票",
    "高铁",
    "签证",
    "美食",
    "天气",
    "预算",
    "攻略",
    "古城",
    "寺庙",
    "寺",
    "博物馆",
    "出发",
    "自由行",
    "度假",
)
_NON_TRAVEL_TERMS = (
    "python",
    "javascript",
    "写代码",
    "编程",
    "股票",
    "基金",
    "彩票",
    "数学题",
    "物理题",
    "化学题",
    "医疗诊断",
    "写论文",
)


class TravelIntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: TravelIntent
    in_scope: bool
    confidence: float = Field(ge=0, le=1)
    selected_skills: list[str] = Field(default_factory=list)
    destination: str | None = Field(default=None, max_length=120)
    place_query: str | None = Field(default=None, max_length=200)
    web_search: bool = False
    read_url: bool = False
    deep_research: bool = False


@dataclass(frozen=True, slots=True)
class TravelChatResult:
    response: TravelChatResponse
    usage: LlmUsage
    skills_used: list[dict[str, object]]
    skill_route: dict[str, object]
    prompt_versions: list[dict[str, str]]


class TravelChatAgent:
    def __init__(
        self,
        *,
        provider: StructuredLlmProvider,
        available_skills: list[SkillManifest],
        tool_registry: ToolRegistry,
        tool_context: ToolContext,
        skill_handlers: Mapping[str, SkillHandler],
        today: datetime | None = None,
    ) -> None:
        self._provider = provider
        self._skills = {skill.name: skill for skill in available_skills}
        self._tool_registry = tool_registry
        self._tool_context = tool_context
        self._handlers = skill_handlers
        self._executor = SkillExecutor()
        self._today = today or datetime.now(UTC)
        self._intent_prompt = load_prompt(TRAVEL_CHAT_INTENT_ROUTER)
        self._answer_prompt = load_prompt(TRAVEL_CHAT_ANSWER)
        self._prompt_safety = PromptSafetyService()

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    async def respond(
        self,
        *,
        owner_id: UUID,
        message: str,
        history: list[ChatHistoryTurn],
        documents: list[tuple[str, str]] | None = None,
        image_data_urls: tuple[str, ...] = (),
    ) -> TravelChatResult:
        # 纯问候先自然回应，再进入更严格的旅行域判断。
        if _is_greeting(message):
            response = TravelChatResponse(
                intent="clarify",
                in_scope=True,
                confidence=0.99,
                answer=_GREETING_ANSWER,
                model_name=self._provider.model_name,
            )
            return TravelChatResult(
                response=response,
                usage=LlmUsage(model_name=self._provider.model_name),
                skills_used=[],
                skill_route={"intent": "clarify", "mode": "greeting"},
                prompt_versions=[],
            )
        if _obviously_non_travel(message):
            decision = TravelIntentDecision(
                intent="out_of_scope",
                in_scope=False,
                confidence=0.99,
            )
            prompt_versions: list[dict[str, str]] = []
        else:
            decision, prompt_versions = await self._route_intent(
                message=message,
                history=history,
            )
        if (
            (documents or image_data_urls)
            and "附件" in message
            and decision.in_scope
        ):
            # 前端在“仅附件、无文字”时使用该提示，应直接进入需求解析。
            decision = decision.model_copy(
                update={
                    "intent": "plan_trip",
                    "selected_skills": [],
                }
            )
        decision.selected_skills = [
            name for name in decision.selected_skills if name in self._skills
        ]
        if not decision.in_scope or decision.intent == "out_of_scope":
            response = TravelChatResponse(
                intent="out_of_scope",
                in_scope=False,
                confidence=decision.confidence,
                answer=_OUT_OF_SCOPE_ANSWER,
                model_name=self._provider.model_name,
            )
            return TravelChatResult(
                response=response,
                usage=LlmUsage(model_name=self._provider.model_name),
                skills_used=[],
                skill_route=decision.model_dump(mode="json"),
                prompt_versions=prompt_versions,
            )

        if decision.intent in {"plan_trip", "clarify"}:
            return await self._plan_response(
                owner_id=owner_id,
                message=message,
                history=history,
                decision=decision,
                documents=documents,
                image_data_urls=image_data_urls,
                prompt_versions=prompt_versions,
            )

        return await self._answer_travel_question(
            owner_id=owner_id,
            message=message,
            history=history,
            decision=decision,
            prompt_versions=prompt_versions,
        )

    async def _route_intent(
        self,
        *,
        message: str,
        history: list[ChatHistoryTurn],
    ) -> tuple[TravelIntentDecision, list[dict[str, str]]]:
        """请求模型给出紧凑路由结果；失败时使用安全兜底。"""
        if self._provider.provider_name == "mock":
            return _heuristic_intent(message), []
        skill_metadata: list[dict[str, object]] = [
            {
                "name": skill.name,
                "description": skill.description,
                "allowed_tools": skill.allowed_tools,
            }
            for skill in self._skills.values()
        ]
        request = LlmRequest(
            system_prompt=self._intent_prompt.content,
            user_prompt=self._intent_user_prompt(
                message=message,
                history=history,
                skill_metadata=skill_metadata,
            ),
            user_text=message,
            response_schema=TravelIntentDecision.model_json_schema(),
            metadata=prompt_request_metadata(
                self._intent_prompt,
                operation="travel_intent",
            ),
            max_tokens=1_000,
        )
        try:
            completion = await self._provider.generate(request)
            raw = json.loads(completion.content)
            return TravelIntentDecision.model_validate(raw), [
                self._intent_prompt.audit_record()
            ]
        except (LlmProviderError, ValueError, ValidationError):
            return _heuristic_intent(message), [self._intent_prompt.audit_record()]

    async def _plan_response(
        self,
        *,
        owner_id: UUID,
        message: str,
        history: list[ChatHistoryTurn],
        decision: TravelIntentDecision,
        documents: list[tuple[str, str]] | None,
        image_data_urls: tuple[str, ...],
        prompt_versions: list[dict[str, str]],
    ) -> TravelChatResult:
        parser = RequirementParser(self._provider, today=self._today.date())
        combined = "\n".join(
            [
                *[turn.content for turn in history if turn.role == "user"],
                message,
            ]
        )
        result = await parser.parse(
            combined,
            documents=documents,
            image_data_urls=image_data_urls,
        )
        response = TravelChatResponse(
            intent=decision.intent,
            in_scope=True,
            confidence=decision.confidence,
            answer=(
                "旅行需求已整理完成，可以开始生成行程。"
                if result.response.brief is not None
                else None
            ),
            selected_skills=decision.selected_skills,
            requires_planning=result.response.brief is not None,
            brief=result.response.brief,
            draft=result.response.draft,
            missing_fields=result.response.missing_fields,
            questions=result.response.questions,
            model_name=result.model_name,
        )
        return TravelChatResult(
            response=response,
            usage=LlmUsage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                model_name=result.model_name,
            ),
            skills_used=[],
            skill_route=decision.model_dump(mode="json"),
            prompt_versions=_merge_prompt_versions(
                prompt_versions,
                result.prompt_versions,
            ),
        )

    async def _answer_travel_question(
        self,
        *,
        owner_id: UUID,
        message: str,
        history: list[ChatHistoryTurn],
        decision: TravelIntentDecision,
        prompt_versions: list[dict[str, str]],
    ) -> TravelChatResult:
        """只执行选中的只读 Tool，再由 DeepSeek 决定是否搜索或读取网页。"""
        tool_context_text = ""
        skills_used: list[dict[str, object]] = []
        audit_start = len(self._tool_context.runner.audits)
        if (
            "destination-research" in decision.selected_skills
            and "destination-research" in self._handlers
        ):
            # Tool 结果属于不可信上下文；先过滤异地同名 POI，再交给模型。
            manifest = self._skills["destination-research"]
            handler = self._handlers["destination-research"]
            destination_input = DestinationResearchInput(
                query=decision.place_query or message[:200],
                city=decision.destination,
                limit=3,
            )
            try:
                result = await self._executor.execute(
                    manifest,
                    SkillContext(
                        tool_registry=self._tool_registry,
                        tool_context=self._tool_context,
                        handler=handler,
                    ),
                    destination_input,
                )
                output = DestinationResearchOutput.model_validate(result.output)
                places = output.places
                if decision.destination:
                    places = [
                        place
                        for place in places
                        if decision.destination
                        in " ".join(
                            [
                                place.name,
                                place.address or "",
                                place.category or "",
                            ]
                        )
                    ]
                tool_context_text = json.dumps(
                    {
                        "places": [
                            place.model_dump(mode="json")
                            for place in places
                        ]
                    },
                    ensure_ascii=False,
                ) if places else ""
                skills_used.append(
                    {
                        "name": result.skill_name,
                        "version": result.version,
                        "status": result.status,
                    }
                )
            except Exception:
                tool_context_text = ""
        used_tools = list(
            dict.fromkeys(
                audit.tool_name
                for audit in self._tool_context.runner.audits[audit_start:]
            )
        )
        if self._provider.provider_name == "mock":
            answer = (
                "这是旅行相关建议。当前为本地演示模式，"
                "实时景点、交通和开放信息请以官方来源为准。"
            )
            usage = LlmUsage(model_name=self._provider.model_name)
            model_name = self._provider.model_name
            sources: list[ChatSourceCitation] = []
        else:
            completion = await self._provider.generate(
                LlmRequest(
                    system_prompt=self._answer_prompt.content,
                    user_prompt=self._answer_user_prompt(
                        message=message,
                        history=history,
                        tool_context_text=tool_context_text,
                    ),
                    user_text=message,
                    response_schema={"type": "object"},
                    metadata=prompt_request_metadata(
                        self._answer_prompt,
                        operation="travel_answer",
                    ),
                    max_tokens=24_000,
                    json_mode=False,
                    web_search=decision.web_search,
                    read_url=decision.read_url,
                    thinking_enabled=decision.deep_research,
                )
            )
            answer = completion.content
            usage = completion.usage
            model_name = completion.usage.model_name or self._provider.model_name
            sources = [
                ChatSourceCitation(
                    url=source.url,
                    title=source.title,
                    cited_text=source.cited_text,
                    published_at=source.published_at,
                )
                for source in completion.sources
            ]
            if not sources and (decision.web_search or decision.read_url):
                answer = f"{answer}\n\n实时信息暂未获得可引用来源，请以官方渠道为准。"

        response = TravelChatResponse(
            intent=decision.intent,
            in_scope=True,
            confidence=decision.confidence,
            answer=answer,
            sources=sources,
            selected_skills=decision.selected_skills,
            used_tools=used_tools,
            model_name=model_name,
        )
        return TravelChatResult(
            response=response,
            usage=usage,
            skills_used=skills_used,
            skill_route=decision.model_dump(mode="json"),
            prompt_versions=_merge_prompt_versions(
                prompt_versions,
                [self._answer_prompt.audit_record()]
                if self._provider.provider_name != "mock"
                else [],
            ),
        )

    def _intent_user_prompt(
        self,
        *,
        message: str,
        history: list[ChatHistoryTurn],
        skill_metadata: list[dict[str, object]],
    ) -> str:
        return (
            f"今天：{self._today.date().isoformat()}\n"
            "可用 Skills："
            f"{json.dumps(skill_metadata, ensure_ascii=False)}\n"
            "历史对话：\n"
            f"{self._prompt_safety.wrap_untrusted('chat-history', _history_text(history))}\n"
            "当前用户消息：\n"
            f"{self._prompt_safety.wrap_untrusted('current-message', message)}\n"
            "只输出符合 schema 的 JSON。"
        )

    def _answer_user_prompt(
        self,
        *,
        message: str,
        history: list[ChatHistoryTurn],
        tool_context_text: str,
    ) -> str:
        return (
            "历史对话：\n"
            f"{self._prompt_safety.wrap_untrusted('chat-history', _history_text(history))}\n"
            "当前问题：\n"
            f"{self._prompt_safety.wrap_untrusted('current-message', message)}\n"
            "地点工具结果：\n"
            f"{self._prompt_safety.wrap_untrusted('tool-results', tool_context_text or '无')}\n"
            "用中文回答，必要时分点；事实尽量引用来源。"
        )


def _history_text(history: list[ChatHistoryTurn]) -> str:
    if not history:
        return "无"
    return "\n".join(
        f"{turn.role}: {turn.content[:1_000]}" for turn in history[-12:]
    )


def _merge_prompt_versions(
    *groups: list[dict[str, str]],
) -> list[dict[str, str]]:
    merged: dict[tuple[str, str, str], dict[str, str]] = {}
    for group in groups:
        for prompt in group:
            key = (
                prompt["agent"],
                prompt["prompt_id"],
                prompt["version"],
            )
            merged[key] = prompt
    return list(merged.values())


def _heuristic_intent(message: str) -> TravelIntentDecision:
    """Mock 模式或路由结果非法时使用的确定性兜底。"""
    normalized = message.strip()
    if not any(term in normalized for term in _TRAVEL_TERMS) and not re.search(
        r"(?:去|到|前往)[\u4e00-\u9fa5]{2,12}",
        normalized,
    ):
        return TravelIntentDecision(
            intent="out_of_scope",
            in_scope=False,
            confidence=0.98,
        )

    destination_match = re.search(
        r"(?:去|到|前往)(?P<destination>[\u4e00-\u9fa5]{2,12})",
        normalized,
    )
    destination = (
        destination_match.group("destination")
        if destination_match is not None
        else None
    )
    is_plan = bool(
        re.search(
            r"\d{4}年|\d{1,2}月\d{1,2}日|"
            r"[一二两三四五六七八九十\d]+个人|预算|规划|安排|行程|几天|三天|两天",
            normalized,
        )
    )
    if is_plan or re.search(r"(?:去|到|前往)[\u4e00-\u9fa5]{2,12}", normalized):
        return TravelIntentDecision(
            intent="plan_trip",
            in_scope=True,
            confidence=0.9,
            destination=destination,
        )
    if any(term in normalized for term in ("预算", "花费", "费用", "超支")):
        return TravelIntentDecision(
            intent="budget_advice",
            in_scope=True,
            confidence=0.82,
            selected_skills=["budget-optimization"],
            destination=destination,
            web_search=False,
        )
    if any(term in normalized for term in ("路线", "交通", "怎么走", "地铁", "公交")):
        return TravelIntentDecision(
            intent="route_advice",
            in_scope=True,
            confidence=0.82,
            selected_skills=["route-optimization"],
            destination=destination,
            web_search=True,
            read_url=True,
        )
    return TravelIntentDecision(
        intent="destination_research",
        in_scope=True,
        confidence=0.84,
        selected_skills=["destination-research"],
        destination=destination,
        place_query=normalized[:200],
        web_search=True,
        read_url=True,
        deep_research=any(
            term in normalized
            for term in ("最新", "开放时间", "门票", "官网", "政策", "安全")
        ),
    )


def _obviously_non_travel(message: str) -> bool:
    """在消耗模型调用前拦截明显的非旅行任务。"""
    normalized = message.lower()
    return any(term in normalized for term in _NON_TRAVEL_TERMS)


def _is_greeting(message: str) -> bool:
    return re.fullmatch(
        r"\s*(?:你好|您好|嗨|hi|hello|早上好|下午好|晚上好)"
        r"(?:[呀啊哈，,\s]*)(?:[！!。.]*)\s*",
        message,
        flags=re.IGNORECASE,
    ) is not None
