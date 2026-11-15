# 文件说明：LangGraph 编排：travel_graph。
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agents.itinerary_composer import (
    ItineraryComposer,
    MockItineraryComposer,
    create_itinerary_composer,
)
from app.agents.research_planner import (
    MockResearchPlanner,
    ResearchPlanner,
    create_research_planner,
)
from app.core.config import Settings
from app.graph.nodes.build_itinerary import build_itinerary_node
from app.graph.nodes.evaluator import evaluator_node
from app.graph.nodes.evidence_plan import evidence_plan_node
from app.graph.nodes.evidence_verify import evidence_verify_node
from app.graph.nodes.parse_request import parse_request_node
from app.graph.nodes.persist_plan import persist_plan_node
from app.graph.nodes.repair import repair_node
from app.graph.nodes.research import research_node
from app.graph.nodes.skill_execute import skill_execute_node
from app.graph.nodes.skill_finalize import skill_finalize_node
from app.graph.nodes.skill_route import skill_route_node
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.providers.base import MapProvider
from app.schemas.ai import (
    ItineraryDraftContract,
    PlanningEventContract,
    TripBriefContract,
    ValidationIssueContract,
)
from app.services.place_service import create_map_provider
from app.skills.manifest import SkillManifest
from app.skills.registry import load_configured_registry
from app.skills.router import SkillRouter
from app.skills.runtime import SkillRuntime
from app.tools.base import ToolCallAudit
from app.tools.budget_tools import BudgetTool
from app.tools.context import EvidenceWriter
from app.tools.place_tools import PlaceTool
from app.tools.route_tools import RouteTool


@dataclass(frozen=True, slots=True)
class GraphLimits:
    max_loops: int = 2
    max_tool_calls: int = 12
    timeout_seconds: float = 120.0
    max_cost_minor: int = 1_000

    def __post_init__(self) -> None:
        if self.max_loops < 0 or self.max_loops > 2:
            raise ValueError("max_loops must be between 0 and 2")
        if self.max_tool_calls < 1 or self.max_tool_calls > 12:
            raise ValueError("max_tool_calls must be between 1 and 12")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_cost_minor < 0:
            raise ValueError("max_cost_minor cannot be negative")


@dataclass(frozen=True, slots=True)
class TravelGraphOutcome:
    status: str
    draft: ItineraryDraftContract | None
    issues: list[ValidationIssueContract]
    events: list[PlanningEventContract]
    tool_audits: list[ToolCallAudit]
    state: TravelGraphState
    error_code: str | None
    error_message: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model_name: str
    provider_name: str
    estimated_cost_minor: int
    skills_used: list[dict[str, object]]
    skill_route: dict[str, object] | None
    prompt_versions: list[dict[str, str]]


class TravelGraph:
    def __init__(
        self,
        *,
        map_provider: MapProvider,
        composer: ItineraryComposer | None,
        research_planner: ResearchPlanner | None = None,
        skill_router: SkillRouter | None = None,
        available_skills: list[SkillManifest] | None = None,
        limits: GraphLimits,
    ) -> None:
        self._map_provider = map_provider
        self._composer = composer or MockItineraryComposer()
        self._research_planner = research_planner or MockResearchPlanner()
        self._skill_router = skill_router or SkillRouter()
        self._available_skills = available_skills or []
        self._limits = limits

    @property
    def provider_name(self) -> str:
        return self._composer.provider_name

    @property
    def model_name(self) -> str:
        return self._composer.model_name

    async def run(
        self,
        *,
        trip_id: str,
        version: int,
        brief: TripBriefContract,
        brief_confirmed: bool,
        thread_id: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        resume: bool = False,
        owner_id: UUID | None = None,
        evidence_writer: EvidenceWriter | None = None,
        available_skills: list[SkillManifest] | None = None,
        skills_enabled: bool = True,
        router_enabled: bool = True,
        skill_runtime: SkillRuntime | None = None,
        on_update: Callable[[TravelGraphState], Awaitable[None]] | None = None,
    ) -> TravelGraphOutcome:
        # 每次运行创建独立 Runtime，隔离 Tool 预算、权限和审计。
        deadline = datetime.now(UTC) + timedelta(seconds=self._limits.timeout_seconds)
        runtime = GraphRuntime(
            max_tool_calls=self._limits.max_tool_calls,
            deadline=deadline,
            owner_id=owner_id,
            evidence_writer=evidence_writer,
            allowed_tools={
                PlaceTool.name,
                RouteTool.name,
                BudgetTool.name,
            },
            provider_permissions={"map", "deterministic"},
        )
        place_tool = PlaceTool(self._map_provider, runtime.tool_context)
        route_tool = RouteTool(self._map_provider, runtime.tool_context)
        budget_tool = BudgetTool(runtime.tool_context)
        runtime.tool_registry.register(PlaceTool.spec(), place_tool.invoke)
        runtime.tool_registry.register(RouteTool.spec(), route_tool.invoke)
        runtime.tool_registry.register(BudgetTool.spec(), budget_tool.invoke)
        # 注册三个确定性 Tool 后编译本轮 Graph。
        graph = self._compile(
            runtime=runtime,
            place_tool=place_tool,
            route_tool=route_tool,
            budget_tool=budget_tool,
            available_skills=(
                available_skills
                if available_skills is not None
                else self._available_skills
            ),
            skills_enabled=skills_enabled,
            router_enabled=router_enabled,
            skill_runtime=skill_runtime,
            checkpointer=checkpointer,
        )
        initial: TravelGraphState = {
            "trip_id": trip_id,
            "version": version,
            "brief": brief.model_dump(mode="json"),
            "brief_confirmed": brief_confirmed,
            "candidates": [],
            "evidence_ids_by_place": {},
            "evidence_records": [],
            "evidence_issues": [],
            "draft": None,
            "issues": [],
            "loop_count": 0,
            "composer_attempts": 0,
            "tool_call_count": 0,
            "deadline_at": deadline.isoformat(),
            "status": "running",
            "error_code": None,
            "error_message": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0,
            "estimated_cost_minor": 0,
            "model_name": self._composer.model_name,
            "provider_name": self._composer.provider_name,
            "skills_used": [],
            "skill_results": {},
            "skill_errors": {},
            "skill_route": None,
            "prompt_versions": [],
            "events": [],
        }
        # thread_id 同时用于 LangGraph checkpoint 和恢复同一运行。
        config: RunnableConfig | None = (
            {"configurable": {"thread_id": thread_id}}
            if thread_id is not None
            else None
        )
        input_state: TravelGraphState | None = initial
        # resume 只透传 None 让 LangGraph 读取既有 checkpoint；不存在时才发送初始状态。
        if resume and checkpointer is not None and config is not None:
            checkpoint = await checkpointer.aget_tuple(config)
            input_state = None if checkpoint is not None else initial
        try:
            final_state = initial
            async with asyncio.timeout(self._limits.timeout_seconds):
                async for update in graph.astream(
                    input_state,
                    config,
                    stream_mode="values",
                ):
                    final_state = cast(TravelGraphState, update)
                    if on_update is not None:
                        await on_update(final_state)
        except TimeoutError:
            runtime.emit("error", status="failed", message="规划任务超过总时限")
            final_state = {
                **initial,
                "status": "failed",
                "error_code": "graph_timeout",
                "error_message": "Graph deadline exceeded",
                "tool_call_count": runtime.tools.call_count,
            }
        return self._outcome(final_state, runtime)

    def _compile(
        self,
        *,
        runtime: GraphRuntime,
        place_tool: PlaceTool,
        route_tool: RouteTool,
        budget_tool: BudgetTool,
        available_skills: list[SkillManifest],
        skills_enabled: bool,
        router_enabled: bool,
        skill_runtime: SkillRuntime | None,
        checkpointer: BaseCheckpointSaver | None,
    ):
        builder = StateGraph(TravelGraphState)
        builder.add_node(
            "parse_request",
            partial(parse_request_node, graph_runtime=runtime),
        )
        builder.add_node(
            "skill_route",
            partial(
                skill_route_node,
                graph_runtime=runtime,
                router=self._skill_router,
                available_skills=available_skills,
                skills_enabled=skills_enabled,
                router_enabled=router_enabled,
            ),
        )
        builder.add_node(
            "research",
            partial(
                research_node,
                graph_runtime=runtime,
                place_tool=place_tool,
                research_planner=self._research_planner,
            ),
        )
        builder.add_node(
            "skill_execute",
            partial(
                skill_execute_node,
                graph_runtime=runtime,
                skill_runtime=skill_runtime,
            ),
        )
        builder.add_node(
            "evidence_plan",
            partial(
                evidence_plan_node,
                graph_runtime=runtime,
            ),
        )
        builder.add_node(
            "build_itinerary",
            partial(
                build_itinerary_node,
                graph_runtime=runtime,
                composer=self._composer,
                max_loops=self._limits.max_loops,
                max_cost_minor=self._limits.max_cost_minor,
            ),
        )
        builder.add_node(
            "skill_finalize",
            partial(
                skill_finalize_node,
                graph_runtime=runtime,
                skill_runtime=skill_runtime,
            ),
        )
        builder.add_node(
            "evidence_verify",
            partial(
                evidence_verify_node,
                graph_runtime=runtime,
                skill_runtime=skill_runtime,
            ),
        )
        builder.add_node(
            "evaluator",
            partial(
                evaluator_node,
                graph_runtime=runtime,
                route_tool=route_tool,
                budget_tool=budget_tool,
                max_repairs=self._limits.max_loops,
            ),
        )
        builder.add_node(
            "repair",
            partial(repair_node, graph_runtime=runtime),
        )
        builder.add_node(
            "persist_plan",
            partial(persist_plan_node, graph_runtime=runtime),
        )
        builder.add_edge(START, "parse_request")
        builder.add_conditional_edges(
            "parse_request",
            _after_parse,
            {"route": "skill_route", "persist": "persist_plan"},
        )
        builder.add_conditional_edges(
            "skill_route",
            _after_skill_route,
            {"research": "research", "persist": "persist_plan"},
        )
        builder.add_edge("research", "skill_execute")
        builder.add_edge("skill_execute", "evidence_plan")
        builder.add_conditional_edges(
            "evidence_plan",
            _after_evidence_plan,
            {"build": "build_itinerary", "persist": "persist_plan"},
        )
        builder.add_conditional_edges(
            "build_itinerary",
            _after_build,
            {
                "retry": "build_itinerary",
                "verify": "skill_finalize",
                "failed": "persist_plan",
            },
        )
        builder.add_edge("skill_finalize", "evidence_verify")
        builder.add_conditional_edges(
            "evidence_verify",
            _after_evidence_verify,
            {"evaluate": "evaluator", "persist": "persist_plan"},
        )
        builder.add_conditional_edges(
            "evaluator",
            _after_evaluator,
            {"repair": "repair", "persist": "persist_plan"},
        )
        builder.add_edge("repair", "evaluator")
        builder.add_edge("persist_plan", END)
        return builder.compile(
            checkpointer=checkpointer,
            name="tripmate-travel-graph",
        )

    @staticmethod
    def _outcome(
        state: TravelGraphState,
        runtime: GraphRuntime,
    ) -> TravelGraphOutcome:
        raw_events = runtime.events
        if not raw_events:
            raw_events = [
                PlanningEventContract.model_validate(event)
                for event in state.get("events", [])
            ]
        draft_payload = state.get("draft")
        draft = (
            ItineraryDraftContract.model_validate(draft_payload)
            if state.get("status") in {"completed", "partial"}
            and draft_payload is not None
            else None
        )
        skill_route = state.get("skill_route")
        return TravelGraphOutcome(
            status=str(state.get("status") or "failed"),
            draft=draft,
            issues=[
                ValidationIssueContract.model_validate(item)
                for item in state.get("issues", [])
            ],
            events=raw_events,
            tool_audits=list(runtime.tools.audits),
            state={
                **state,
                "tool_call_count": runtime.tools.call_count,
                "events": runtime.event_dicts(),
            },
            error_code=state.get("error_code"),
            error_message=state.get("error_message"),
            input_tokens=int(state.get("input_tokens", 0)),
            output_tokens=int(state.get("output_tokens", 0)),
            latency_ms=int(state.get("latency_ms", 0)),
            model_name=str(state.get("model_name") or ""),
            provider_name=str(state.get("provider_name") or ""),
            estimated_cost_minor=int(state.get("estimated_cost_minor", 0)),
            skills_used=[
                dict(item) for item in state.get("skills_used", [])
            ],
            skill_route=(
                dict(skill_route) if skill_route is not None else None
            ),
            prompt_versions=[
                dict(item) for item in state.get("prompt_versions", [])
            ],
        )


def _after_parse(state: TravelGraphState) -> str:
    return "route" if state.get("status") == "running" else "persist"


def _after_skill_route(state: TravelGraphState) -> str:
    return "research" if state.get("status") == "running" else "persist"


def _after_evidence_plan(state: TravelGraphState) -> str:
    return "build" if state.get("status") == "running" else "persist"


def _after_build(state: TravelGraphState) -> str:
    if state.get("status") == "retrying":
        return "retry"
    if state.get("status") == "completed":
        return "verify"
    return "failed"


def _after_evidence_verify(state: TravelGraphState) -> str:
    return (
        "persist"
        if state.get("status") in {"partial", "failed"}
        else "evaluate"
    )


def _after_evaluator(state: TravelGraphState) -> str:
    return "repair" if state.get("status") == "repairing" else "persist"


def create_travel_graph(
    settings: Settings,
    *,
    research_settings: Settings | None = None,
    composer_settings: Settings | None = None,
) -> TravelGraph:
    research_settings = research_settings or settings
    composer_settings = composer_settings or settings
    skill_registry = load_configured_registry(settings)
    return TravelGraph(
        map_provider=create_map_provider(settings),
        composer=create_itinerary_composer(composer_settings),
        research_planner=create_research_planner(research_settings),
        skill_router=SkillRouter(),
        available_skills=skill_registry.latest_manifests(),
        limits=GraphLimits(
            max_loops=settings.planning_max_loops,
            max_tool_calls=settings.planning_max_tool_calls,
            timeout_seconds=settings.planning_timeout_seconds,
            max_cost_minor=settings.planning_max_cost_minor,
        ),
    )
