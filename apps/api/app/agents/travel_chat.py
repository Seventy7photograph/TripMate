# 文件说明：AI Agent：travel_chat。
"""旅行对话路由，并按需接入可追溯的 Web 研究能力。"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from app.agents.requirement_parser import RequirementParser
from app.domain.travel_dates import DateResolution, resolve_travel_dates
from app.domain.travel_intent import (
    classify_travel_signals,
    is_explicit_trip_plan_request,
    is_obviously_non_travel,
)
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
from app.schemas.planning_draft import PlanningDraft
from app.services.prompt_safety import PromptSafetyService
from app.skills.executor import SkillContext, SkillExecutor, SkillHandler
from app.skills.manifest import SkillManifest
from app.skills.production import (
    AttachmentUnderstandingOutput,
    DestinationResearchInput,
    DestinationResearchOutput,
    TripIntentRoutingOutput,
)
from app.tools.base import ToolCallAudit
from app.tools.context import ToolContext
from app.tools.place_tools import SearchPlacesOutput
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

class TravelSkillCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, object] = Field(default_factory=dict)


class TravelIntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: TravelIntent
    in_scope: bool
    confidence: float = Field(ge=0, le=1)
    selected_skills: list[str] = Field(default_factory=list)
    skill_calls: list[TravelSkillCall] = Field(
        default_factory=list,
        max_length=6,
    )
    origin: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    place_query: str | None = Field(default=None, max_length=200)
    web_search: bool = False
    read_url: bool = False
    deep_research: bool = False

    @model_validator(mode="after")
    def synchronize_selected_skills(self) -> "TravelIntentDecision":
        called = [call.name for call in self.skill_calls]
        if called:
            self.selected_skills = list(
                dict.fromkeys([*self.selected_skills, *called])
            )
        return self


def _apply_routing_skill_output(
    decision: TravelIntentDecision,
    output: TripIntentRoutingOutput | None,
) -> TravelIntentDecision:
    if output is None:
        return decision
    updates: dict[str, object] = {
        "selected_skills": list(
            dict.fromkeys(
                [*decision.selected_skills, *output.selected_skills]
            )
        )
    }
    if decision.confidence < 0.7 or decision.intent == "clarify":
        intent_map: dict[str, TravelIntent] = {
            "create_trip_plan": "plan_trip",
            "understand_attachment": "travel_question",
            "answer_travel_question": "travel_question",
            "recommend_options": "travel_question",
            "social_copywriting": "travel_question",
            "emergency_information": "travel_question",
            "clarify": "clarify",
            "unsupported": "out_of_scope",
        }
        updates["intent"] = intent_map[output.intent]
        updates["in_scope"] = output.intent != "unsupported"
        updates["confidence"] = max(
            decision.confidence,
            output.confidence,
        )
    return decision.model_copy(update=updates)


def should_recover_scope(
    decision: TravelIntentDecision,
    message: str,
) -> bool:
    signal = classify_travel_signals(message)
    return (
        decision.intent == "out_of_scope"
        and signal.in_scope
        and not is_obviously_non_travel(message)
    )


@dataclass(frozen=True, slots=True)
class TravelChatResult:
    response: TravelChatResponse
    usage: LlmUsage
    skills_used: list[dict[str, object]]
    tool_audits: list[ToolCallAudit]
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
        attachment_ids: list[UUID] | None = None,
        planning_draft: PlanningDraft | None = None,
        today: date | None = None,
    ) -> TravelChatResult:
        effective_today = today or self._today.date()
        draft_record = (
            None
            if planning_draft is None
            else planning_draft.model_dump(
                mode="json",
                exclude_none=True,
                exclude_defaults=True,
            )
        )
        message_dates = resolve_travel_dates(
            message,
            today=effective_today,
        )
        date_resolution = resolve_travel_dates(
            message,
            today=effective_today,
            history=tuple(
                turn.content for turn in history if turn.role == "user"
            ),
            draft=draft_record,
        )
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
                tool_audits=[],
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
                planning_draft=planning_draft,
                today=effective_today,
            )
        if (
            planning_draft is not None
            and bool(draft_record)
            and (
                message_dates.start_date is not None
                or message_dates.duration_days is not None
            )
        ):
            decision = TravelIntentDecision(
                intent="plan_trip",
                in_scope=True,
                confidence=max(decision.confidence, 0.92),
                destination=decision.destination or planning_draft.destination,
            )
        if is_explicit_trip_plan_request(message):
            heuristic = _heuristic_intent(message)
            if heuristic.in_scope and heuristic.intent == "plan_trip":
                decision = heuristic
        elif should_recover_scope(decision, message):
            heuristic = _heuristic_intent(message)
            if heuristic.in_scope:
                decision = heuristic
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
                tool_audits=[],
                skill_route=decision.model_dump(mode="json"),
                prompt_versions=prompt_versions,
            )

        routing_skill_used, routing_output = await self._execute_routing_skill(
            message
        )
        decision = _apply_routing_skill_output(
            decision,
            routing_output,
        )
        if decision.intent in {"plan_trip", "clarify"}:
            return await self._plan_response(
                owner_id=owner_id,
                message=message,
                history=history,
                decision=decision,
                documents=documents,
                image_data_urls=image_data_urls,
                attachment_ids=attachment_ids or [],
                prompt_versions=prompt_versions,
                routing_skill_used=routing_skill_used,
                planning_draft=planning_draft,
                date_resolution=date_resolution,
                today=effective_today,
            )

        return await self._answer_travel_question(
            owner_id=owner_id,
            message=message,
            history=history,
            decision=decision,
            prompt_versions=prompt_versions,
            routing_skill_used=routing_skill_used,
        )

    async def _execute_routing_skill(
        self,
        message: str,
    ) -> tuple[dict[str, object] | None, TripIntentRoutingOutput | None]:
        manifest = self._skills.get("trip-intent-routing")
        handler = self._handlers.get("trip-intent-routing")
        if manifest is None or handler is None:
            return None, None
        try:
            result = await self._executor.execute(
                manifest,
                SkillContext(
                    tool_registry=self._tool_registry,
                    tool_context=self._tool_context,
                    handler=handler,
                ),
                {
                    "text": message,
                    "available_skills": sorted(self._skills),
                },
            )
        except Exception:
            return None, None
        return (
            {
                "name": result.skill_name,
                "version": result.version,
                "status": result.status,
            },
            TripIntentRoutingOutput.model_validate(result.output),
        )

    async def _route_intent(
        self,
        *,
        message: str,
        history: list[ChatHistoryTurn],
        planning_draft: PlanningDraft | None,
        today: date,
    ) -> tuple[TravelIntentDecision, list[dict[str, str]]]:
        """请求模型给出紧凑路由结果；失败时使用安全兜底。"""
        if self._provider.provider_name == "mock":
            return _heuristic_intent(message), []
        skill_metadata: list[dict[str, object]] = [
            {
                "name": skill.name,
                "description": skill.description,
                "input_schema": skill.input_schema,
                "allowed_tools": skill.allowed_tools,
                "allowed_mcp_connectors": skill.allowed_mcp_connectors,
            }
            for skill in self._skills.values()
        ]
        request = LlmRequest(
            system_prompt=self._intent_prompt.content,
            user_prompt=self._intent_user_prompt(
                message=message,
                history=history,
                skill_metadata=skill_metadata,
                planning_draft=planning_draft,
                today=today,
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
        attachment_ids: list[UUID],
        prompt_versions: list[dict[str, str]],
        routing_skill_used: dict[str, object] | None,
        planning_draft: PlanningDraft | None,
        date_resolution: DateResolution,
        today: date,
    ) -> TravelChatResult:
        skills_used = (
            [routing_skill_used] if routing_skill_used is not None else []
        )
        used_tools: list[str] = []
        audit_start = len(self._tool_context.runner.audits)
        attachment_missing_fields: list[str] = []
        if attachment_ids:
            manifest = self._skills.get("attachment-understanding")
            handler = self._handlers.get("attachment-understanding")
            if manifest is not None and handler is not None:
                attachment_result = await self._executor.execute(
                    manifest,
                    SkillContext(
                        tool_registry=self._tool_registry,
                        tool_context=self._tool_context,
                        handler=handler,
                    ),
                    {"asset_ids": [str(item) for item in attachment_ids]},
                )
                skills_used.append(
                    {
                        "name": attachment_result.skill_name,
                        "version": attachment_result.version,
                        "status": attachment_result.status,
                    }
                )
                attachment_output = (
                    AttachmentUnderstandingOutput.model_validate(
                        attachment_result.output
                    )
                )
                attachment_missing_fields = list(
                    dict.fromkeys(
                        field
                        for field in attachment_output.missing_fields
                        if field
                        in {
                            "destination",
                            "start_date",
                            "end_date",
                            "party_size",
                            "budget_minor",
                        }
                    )
                )
                used_tools = list(
                    dict.fromkeys(
                        audit.tool_name
                        for audit in self._tool_context.runner.audits[
                            audit_start:
                        ]
                    )
                )
                decision.selected_skills = list(
                    dict.fromkeys(
                        [
                            *decision.selected_skills,
                            "attachment-understanding",
                        ]
                    )
                )
        parser = RequirementParser(self._provider, today=today)
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
            previous_draft=planning_draft,
            date_resolution=date_resolution,
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
            used_tools=used_tools,
            requires_planning=result.response.brief is not None,
            brief=result.response.brief,
            draft=result.planning_draft,
            date_assumptions=result.date_assumptions,
            missing_fields=list(
                dict.fromkeys(
                    [
                        *attachment_missing_fields,
                        *result.response.missing_fields,
                    ]
                )
            ),
            questions=list(
                dict.fromkeys(
                    [
                        *[
                            f"附件未提供：{field}"
                            for field in attachment_missing_fields
                        ],
                        *result.response.questions,
                    ]
                )
            ),
            model_name=result.model_name,
        )
        tool_audits = self._tool_context.runner.audits[audit_start:]
        return TravelChatResult(
            response=response,
            usage=LlmUsage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                model_name=result.model_name,
            ),
            skills_used=skills_used,
            tool_audits=list(tool_audits),
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
        routing_skill_used: dict[str, object] | None,
    ) -> TravelChatResult:
        """只执行选中的只读 Tool，再由 DeepSeek 决定是否搜索或读取网页。"""
        tool_context_text = ""
        skills_used: list[dict[str, object]] = (
            [routing_skill_used] if routing_skill_used is not None else []
        )
        skill_results: dict[str, object] = {}
        skill_errors: dict[str, str] = {}
        audit_start = len(self._tool_context.runner.audits)
        self._ensure_memory_skill_call(decision, message)
        self._ensure_social_skill_call(decision, message)
        self._ensure_food_skill_call(decision, message)
        self._ensure_lodging_skill_call(decision)
        self._ensure_weather_skill_call(decision, message)
        self._ensure_safety_skill_call(decision, message)
        await self._ensure_route_skill_call(decision, message)
        called_skills = {call.name for call in decision.skill_calls}
        for call in decision.skill_calls:
            manifest = self._skills.get(call.name)
            handler = self._handlers.get(call.name)
            if manifest is None or handler is None:
                skill_errors[call.name] = "skill_not_registered"
                continue
            try:
                result = await self._executor.execute(
                    manifest,
                    SkillContext(
                        tool_registry=self._tool_registry,
                        tool_context=self._tool_context,
                        handler=handler,
                    ),
                    call.arguments,
                )
                skill_results[call.name] = result.output.model_dump(mode="json")
                skills_used.append(
                    {
                        "name": result.skill_name,
                        "version": result.version,
                        "status": result.status,
                    }
                )
            except Exception as exc:
                fallback = str(
                    getattr(exc, "fallback", manifest.fallback)
                )
                skill_errors[call.name] = (
                    f"{type(exc).__name__}:{fallback}"
                )
                skills_used.append(
                    {
                        "name": call.name,
                        "version": manifest.version,
                        "status": "failed",
                        "error": type(exc).__name__,
                        "fallback": fallback,
                    }
                )
        if (
            "destination-research" in decision.selected_skills
            and "destination-research" in self._handlers
            and "destination-research" not in called_skills
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
                skill_results["destination-research"] = {
                    "places": [
                        place.model_dump(mode="json")
                        for place in places
                    ]
                }
                skills_used.append(
                    {
                        "name": result.skill_name,
                        "version": result.version,
                        "status": result.status,
                    }
                )
            except Exception:
                skill_errors["destination-research"] = (
                    "destination_research_failed"
                )
        if skill_results or skill_errors:
            tool_context_text = json.dumps(
                {
                    "skill_results": skill_results,
                    "skill_errors": skill_errors,
                },
                ensure_ascii=False,
                default=str,
            )
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
            skill_failures=[
                {"name": name, "error": error}
                for name, error in skill_errors.items()
            ],
            model_name=model_name,
        )
        return TravelChatResult(
            response=response,
            usage=usage,
            skills_used=skills_used,
            tool_audits=list(self._tool_context.runner.audits[audit_start:]),
            skill_route=decision.model_dump(mode="json"),
            prompt_versions=_merge_prompt_versions(
                prompt_versions,
                [self._answer_prompt.audit_record()]
                if self._provider.provider_name != "mock"
                else [],
            ),
        )

    async def _ensure_route_skill_call(
        self,
        decision: TravelIntentDecision,
        message: str,
    ) -> None:
        if (
            "route-optimization" not in decision.selected_skills
            or "route-optimization" not in self._handlers
            or any(
                call.name == "route-optimization"
                for call in decision.skill_calls
            )
        ):
            return
        origin_query, destination_query = _extract_route_endpoints(message)
        origin_query = origin_query or decision.origin
        destination_query = destination_query or decision.destination
        if not origin_query or not destination_query:
            return
        points: list[dict[str, object]] = []
        for query in (origin_query, destination_query):
            try:
                output = SearchPlacesOutput.model_validate(
                    await self._tool_registry.invoke(
                        self._tool_context,
                        "search_places",
                        {
                            "keyword": query,
                            "city": query,
                            "limit": 1,
                        },
                    )
                )
            except Exception:
                return
            if not output.results or output.results[0].location is None:
                return
            location = output.results[0].location
            points.append(
                {
                    "longitude": location.longitude,
                    "latitude": location.latitude,
                    "coordinate_system": location.coordinate_system,
                }
            )
        decision.skill_calls.append(
            TravelSkillCall(
                name="route-optimization",
                arguments={
                    "origin": points[0],
                    "destination": points[1],
                    "mode": _route_mode(message),
                    "city": destination_query,
                },
            )
        )

    def _ensure_food_skill_call(
        self,
        decision: TravelIntentDecision,
        message: str,
    ) -> None:
        if (
            "food-planning" not in decision.selected_skills
            or "food-planning" not in self._handlers
            or any(
                call.name == "food-planning"
                for call in decision.skill_calls
            )
            or not decision.destination
        ):
            return
        decision.skill_calls.append(
            TravelSkillCall(
                name="food-planning",
                arguments={
                    "meal": _meal_from_message(message),
                    "city": decision.destination,
                    "dietary": [],
                    "date": self._today.date().isoformat(),
                    "limit": 2,
                },
            )
        )

    def _ensure_lodging_skill_call(
        self,
        decision: TravelIntentDecision,
    ) -> None:
        if (
            "lodging-area-selection" not in decision.selected_skills
            or "lodging-area-selection" not in self._handlers
            or any(
                call.name == "lodging-area-selection"
                for call in decision.skill_calls
            )
            or not decision.destination
        ):
            return
        decision.skill_calls.append(
            TravelSkillCall(
                name="lodging-area-selection",
                arguments={
                    "city": decision.destination,
                    "preferences": [],
                    "limit": 2,
                },
            )
        )

    def _ensure_weather_skill_call(
        self,
        decision: TravelIntentDecision,
        message: str,
    ) -> None:
        if (
            "weather-and-clothing" not in decision.selected_skills
            or "weather-and-clothing" not in self._handlers
            or any(
                call.name == "weather-and-clothing"
                for call in decision.skill_calls
            )
            or not decision.destination
        ):
            return
        decision.skill_calls.append(
            TravelSkillCall(
                name="weather-and-clothing",
                arguments={
                    "city": decision.destination,
                    "date": _travel_date_from_message(
                        message,
                        self._today.date(),
                    ).isoformat(),
                },
            )
        )

    def _ensure_memory_skill_call(
        self,
        decision: TravelIntentDecision,
        message: str,
    ) -> None:
        if not any(
            term in message
            for term in ("记得", "记忆", "偏好", "以前说过")
        ):
            return
        if (
            "travel-memory" not in self._handlers
            or any(
                call.name == "travel-memory"
                for call in decision.skill_calls
            )
        ):
            return
        decision.selected_skills = list(
            dict.fromkeys([*decision.selected_skills, "travel-memory"])
        )
        decision.skill_calls.append(
            TravelSkillCall(
                name="travel-memory",
                arguments={
                    "query": message[:2_000],
                    "limit": 8,
                },
            )
        )

    def _ensure_social_skill_call(
        self,
        decision: TravelIntentDecision,
        message: str,
    ) -> None:
        if not any(
            term in message
            for term in ("小红书", "朋友圈", "微博", "文案")
        ):
            return
        if (
            "social-copywriting" not in self._handlers
            or any(
                call.name == "social-copywriting"
                for call in decision.skill_calls
            )
        ):
            return
        destination = decision.destination or _copy_destination(message)
        if not destination:
            return
        decision.destination = destination
        decision.selected_skills = list(
            dict.fromkeys(
                [*decision.selected_skills, "social-copywriting"]
            )
        )
        decision.skill_calls.append(
            TravelSkillCall(
                name="social-copywriting",
                arguments={
                    "destination": destination,
                    "platform": _social_platform(message),
                    "tone": "quiet",
                    "confirmed_facts": [],
                    "trip_days": _trip_days_from_message(message),
                },
            )
        )

    def _ensure_safety_skill_call(
        self,
        decision: TravelIntentDecision,
        message: str,
    ) -> None:
        if (
            "safety-briefing" not in decision.selected_skills
            or "safety-briefing" not in self._handlers
            or any(
                call.name == "safety-briefing"
                for call in decision.skill_calls
            )
        ):
            return
        decision.skill_calls.append(
            TravelSkillCall(
                name="safety-briefing",
                arguments={
                    "dates": [
                        _travel_date_from_message(
                            message,
                            self._today.date(),
                        ).isoformat()
                    ],
                    "party": _party_from_message(message),
                    "city": decision.destination,
                    "altitude_m": _altitude_from_message(message),
                },
            )
        )

    def _intent_user_prompt(
        self,
        *,
        message: str,
        history: list[ChatHistoryTurn],
        skill_metadata: list[dict[str, object]],
        planning_draft: PlanningDraft | None,
        today: date,
    ) -> str:
        draft_json = (
            "{}"
            if planning_draft is None
            else json.dumps(
                planning_draft.model_dump(mode="json", exclude_none=True),
                ensure_ascii=False,
            )
        )
        return (
            f"今天：{today.isoformat()}\n"
            "可用 Skills："
            f"{json.dumps(skill_metadata, ensure_ascii=False)}\n"
            "已有规划草稿：\n"
            f"{self._prompt_safety.wrap_untrusted('planning-draft', draft_json)}\n"
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
            "Skill 与工具结果：\n"
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
    signal = classify_travel_signals(normalized)
    if not signal.in_scope:
        return TravelIntentDecision(
            intent="out_of_scope",
            in_scope=False,
            confidence=signal.confidence,
        )

    destination = signal.destination
    confidence = max(signal.confidence, 0.82)
    if signal.topic == "planning" or is_explicit_trip_plan_request(normalized):
        return TravelIntentDecision(
            intent="plan_trip",
            in_scope=True,
            confidence=confidence,
            destination=destination,
        )
    if signal.topic == "budget":
        return TravelIntentDecision(
            intent="budget_advice",
            in_scope=True,
            confidence=confidence,
            selected_skills=["budget-optimization"],
            skill_calls=[
                TravelSkillCall(
                    name="budget-optimization",
                    arguments={
                        "stop_costs_minor": [],
                        "budget_minor": _extract_budget_minor(normalized),
                    },
                )
            ],
            destination=destination,
            web_search=False,
        )
    if signal.topic == "route":
        origin, _ = _extract_route_endpoints(normalized)
        return TravelIntentDecision(
            intent="route_advice",
            in_scope=True,
            confidence=confidence,
            selected_skills=["route-optimization"],
            origin=origin,
            destination=destination,
            web_search=True,
            read_url=True,
        )
    if signal.topic == "transport":
        return TravelIntentDecision(
            intent="plan_trip",
            in_scope=True,
            confidence=confidence,
            destination=destination,
        )
    if any(
        term in normalized
        for term in ("小红书", "朋友圈", "微博", "文案")
    ):
        return TravelIntentDecision(
            intent="travel_question",
            in_scope=True,
            confidence=confidence,
            selected_skills=["social-copywriting"],
            destination=_copy_destination(normalized) or destination,
            web_search=False,
        )
    if signal.topic == "food":
        return TravelIntentDecision(
            intent="destination_research",
            in_scope=True,
            confidence=confidence,
            selected_skills=["food-planning"],
            destination=destination,
            place_query=normalized[:200],
            web_search=True,
            read_url=True,
        )
    if signal.topic in {"lodging", "weather", "policy", "safety"}:
        skill = {
            "lodging": "lodging-area-selection",
            "weather": "weather-and-clothing",
            "policy": None,
            "safety": "safety-briefing",
        }[signal.topic]
        return TravelIntentDecision(
            intent="travel_question",
            in_scope=True,
            confidence=confidence,
            selected_skills=[skill] if skill else [],
            destination=destination,
            web_search=True,
            read_url=signal.topic in {"policy", "safety"},
            deep_research=signal.topic in {"policy", "safety"},
        )
    searchable = normalized.casefold()
    return TravelIntentDecision(
        intent="destination_research",
        in_scope=True,
        confidence=confidence,
        selected_skills=["destination-research"],
        destination=destination,
        place_query=normalized[:200],
        web_search=True,
        read_url=True,
        deep_research=any(
            term in searchable
            for term in ("最新", "开放时间", "门票", "官网", "政策", "安全")
        ),
    )


def _obviously_non_travel(message: str) -> bool:
    """在消耗模型调用前拦截明显的非旅行任务。"""
    return is_obviously_non_travel(message)


def _extract_budget_minor(message: str) -> int | None:
    match = re.search(
        r"(\d+(?:\.\d{1,2})?)\s*(万|千|元|块)?",
        message,
    )
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "万":
        value *= 10_000
    elif unit == "千":
        value *= 1_000
    return int(round(value * 100))


def _extract_route_endpoints(
    message: str,
) -> tuple[str | None, str | None]:
    match = re.search(
        r"(?:从)?(?P<origin>[\u4e00-\u9fa5]{2,12}?)"
        r"(?:到|去|前往)"
        r"(?P<destination>[\u4e00-\u9fa5]{2,12}?)"
        r"(?=怎么走|怎么去|如何到|如何走|路线|导航|车程|交通|$)",
        message,
    )
    if match is None:
        return None, None
    return match.group("origin"), match.group("destination")


def _route_mode(message: str) -> str:
    preferences = (
        ("walking", ("步行", "走路")),
        ("driving", ("自驾", "开车", "驾车")),
        ("bicycling", ("骑行", "自行车")),
        ("bus", ("公交", "巴士")),
        ("subway", ("地铁", "轨交")),
        ("flight", ("飞机", "航班", "飞")),
    )
    for mode, terms in preferences:
        if any(term in message for term in terms):
            return mode
    return "driving"


def _meal_from_message(message: str) -> str:
    if any(term in message for term in ("早餐", "早饭")):
        return "breakfast"
    if any(term in message for term in ("晚餐", "晚饭", "夜宵")):
        return "dinner"
    return "lunch"


def _travel_date_from_message(message: str, today: date) -> date:
    current = today
    if "后天" in message:
        return current + timedelta(days=2)
    if "明天" in message:
        return current + timedelta(days=1)
    full_match = re.search(
        r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日",
        message,
    )
    if full_match is not None:
        return date(
            int(full_match.group("year")),
            int(full_match.group("month")),
            int(full_match.group("day")),
        )
    month_match = re.search(r"(?P<month>\d{1,2})月(?:初)?", message)
    if month_match is not None:
        month = int(month_match.group("month"))
        year = current.year + (1 if month < current.month else 0)
        return date(year, month, 1)
    return current


def _party_from_message(message: str) -> list[str]:
    party: list[str] = []
    labels = {
        "老人": "older_adult",
        "儿童": "child",
        "孩子": "child",
        "孕妇": "pregnant",
        "慢性病": "chronic_condition",
    }
    for label, value in labels.items():
        if label in message:
            party.append(value)
    return party


def _altitude_from_message(message: str) -> float | None:
    match = re.search(r"(\d{3,5})\s*米", message)
    return float(match.group(1)) if match is not None else None


def _copy_destination(message: str) -> str | None:
    match = re.search(
        r"(?:写|做|生成|整理)"
        r"(?:一段|一篇|一份)?"
        r"(?P<destination>[\u4e00-\u9fa5]{2,8}?)"
        r"(?:旅行|旅游|游记|行程)",
        message,
    )
    if match is not None:
        return match.group("destination")
    return None


def _social_platform(message: str) -> str:
    if "小红书" in message:
        return "xiaohongshu"
    if "微博" in message:
        return "weibo"
    if "朋友圈" in message:
        return "wechat_moments"
    return "generic"


def _trip_days_from_message(message: str) -> int | None:
    match = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*天", message)
    if match is None:
        return None
    raw = match.group(1)
    if raw.isdigit():
        return int(raw)
    values = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    return values.get(raw)


def _is_greeting(message: str) -> bool:
    return re.fullmatch(
        r"\s*(?:你好|您好|嗨|hi|hello|早上好|下午好|晚上好)"
        r"(?:[呀啊哈，,\s]*)(?:[！!。.]*)\s*",
        message,
        flags=re.IGNORECASE,
    ) is not None
