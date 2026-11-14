# 文件说明：业务服务：planning_service。
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.itinerary import SourceMetadata
from app.evidence.repository import EvidenceRepository
from app.graph.state import TravelGraphState
from app.graph.travel_graph import TravelGraph, TravelGraphOutcome, create_travel_graph
from app.models.agent_run import AgentRun
from app.models.tool_call_log import ToolCallLog
from app.providers.base import point_from_record
from app.queue.planning_queue import PlanningQueue, create_planning_queue
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.ai import PlanningEventContract, TripBriefContract
from app.services.cost_guard import CostGuard
from app.services.feature_service import FeatureFlagService
from app.services.memory_service import MemoryService
from app.services.version_service import VersionService, VersionTripNotFoundError
from app.skills.registry import load_configured_registry
from app.skills.state_service import SkillStateService


class PlanningTripNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AgentRunView:
    id: UUID
    trip_id: UUID | None
    status: str
    progress: int
    events: list[dict[str, object]]
    result: dict[str, object] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    tool_call_count: int
    loop_count: int
    prompt_versions: list[dict[str, str]]


class PlanningService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        graph: TravelGraph | None = None,
        queue: PlanningQueue | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._graph = graph or create_travel_graph(settings)
        self._queue = queue or create_planning_queue(settings)
        self._checkpointer = checkpointer
        self._versions = VersionService(session)
        self._trips = TripRepository(session)
        self._features = FeatureFlagService(session)
        self._costs = CostGuard(session, settings)

    async def start(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
        apply_to_itinerary: bool = False,
        request_ip_hash: str | None = None,
    ) -> AgentRunView:
        # 先检查功能开关与成本配额，再创建可追踪的 AgentRun。
        await self._features.require_all(
            ["ai_planning", "llm_provider", "map_provider"]
        )
        await self._costs.check(
            owner_id=owner_id,
            provider=self._graph.provider_name,
            request_ip_hash=request_ip_hash,
        )
        # 通过版本行锁确认用户拥有旅行且提交版本仍然有效。
        try:
            trip = await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise PlanningTripNotFoundError from exc

        run = AgentRun(
            trip_id=trip.id,
            created_by=owner_id,
            request_ip_hash=request_ip_hash,
            status="queued",
            progress=0,
            purpose="planning",
            source_version=trip.version,
            apply_to_itinerary=apply_to_itinerary,
            provider=self._graph.provider_name,
            model_name=self._graph.model_name,
            events=[
                PlanningEventContract(
                    sequence=1,
                    type="stage",
                    stage="queued",
                    status="queued",
                    message="规划任务已进入队列",
                ).model_dump(mode="json")
            ],
            tool_call_count=0,
            loop_count=0,
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        await self._session.commit()
        # 入队后由 Worker 执行；inline 队列用于测试和本地确定性运行。
        await self._queue.enqueue(run.id)

        if self._queue.is_inline:
            return await self.run_job(run.id)
        return self._to_view(run)

    async def run_job(self, job_id: UUID) -> AgentRunView:
        # 已完成任务直接返回，避免 Worker 重启后重复生成。
        run = await self._session.get(AgentRun, job_id)
        if run is None:
            raise PlanningTripNotFoundError
        if run.status in {"completed", "failed"}:
            return self._to_view(run)
        if run.trip_id is None:
            run.status = "failed"
            run.progress = 100
            run.error_code = "trip_not_found"
            run.error_message = "Planning job has no trip"
            run.finished_at = datetime.now(UTC)
            run.events = [
                *run.events,
                PlanningEventContract(
                    sequence=len(run.events) + 1,
                    type="error",
                    status="failed",
                    message="规划任务缺少旅行信息",
                ).model_dump(mode="json"),
            ]
            await self._session.commit()
            return self._to_view(run)

        trip = await self._trips.get_for_owner(
            owner_id=run.created_by,
            trip_id=run.trip_id,
        )
        if trip is None:
            run.status = "failed"
            run.progress = 100
            run.error_code = "trip_not_found"
            run.error_message = "Trip not found"
            run.finished_at = datetime.now(UTC)
            await self._session.commit()
            return self._to_view(run)

        # 已开始过的任务使用 checkpoint 恢复，不能重复执行前面的节点。
        was_started = run.status == "running" and run.started_at is not None
        run.status = "running"
        run.progress = 15
        run.started_at = run.started_at or datetime.now(UTC)
        run.events = [
            *run.events,
            PlanningEventContract(
                sequence=len(run.events) + 1,
                type="stage",
                stage="planning",
                status="running",
                message=(
                    "正在从断点恢复规划"
                    if was_started
                    else "正在启动 LangGraph 规划"
                ),
            ).model_dump(mode="json"),
        ]
        await self._session.flush()
        await self._session.commit()

        contract = TripBriefContract.model_validate(trip.brief.to_record())
        memory_service = MemoryService(self._session)
        memory_query = " ".join(
            [
                trip.brief.destination,
                trip.brief.origin or "",
                *trip.brief.interests,
                *trip.brief.lodging_preferences,
            ]
        )
        memory_event: PlanningEventContract | None = None
        try:
            memory_constraints = await memory_service.retrieval_constraints(
                owner_id=run.created_by,
                query=memory_query,
            )
        except SQLAlchemyError:
            memory_constraints = []
            run.events = [
                *run.events,
                PlanningEventContract(
                    sequence=len(run.events) + 1,
                    type="stage",
                    stage="memory_unavailable",
                    status="warning",
                    message="授权旅行记忆暂不可用，已按无记忆继续",
                ).model_dump(mode="json"),
            ]
            await self._session.commit()
        if memory_constraints:
            contract = contract.model_copy(
                update={
                    "constraints": list(
                        dict.fromkeys([*contract.constraints, *memory_constraints])
                    )
                }
            )
            memory_event = PlanningEventContract(
                sequence=len(run.events) + 1,
                type="stage",
                stage="memory_applied",
                status="completed",
                message=f"已应用 {len(memory_constraints)} 条授权旅行记忆",
            )
            run.events = [
                *run.events,
                memory_event.model_dump(mode="json"),
            ]
            await self._session.commit()
        try:
            skill_registry = load_configured_registry(self._settings)
            skills_enabled = await self._features.is_enabled(
                "agent_skills_enabled"
            )
            router_enabled = await self._features.is_enabled(
                "agent_skill_router_enabled"
            )
            available_skills = (
                await SkillStateService(self._session).enabled_manifests(
                    skill_registry
                )
                if skills_enabled
                else []
            )
            outcome = await self._graph.run(
                trip_id=str(trip.id),
                version=run.source_version,
                brief=contract,
                brief_confirmed=True,
                thread_id=str(run.id),
                checkpointer=self._checkpointer,
                resume=was_started,
                owner_id=run.created_by,
                evidence_writer=EvidenceRepository(self._session),
                available_skills=available_skills,
                skills_enabled=skills_enabled,
                router_enabled=router_enabled,
                on_update=lambda state: self._persist_progress(
                    job_id,
                    state,
                ),
            )
            # 只有用户明确要求且生成完整时才写入正式逐日行程。
            if run.apply_to_itinerary and outcome.status == "completed":
                await self._apply_itinerary(
                    owner_id=run.created_by,
                    trip_id=trip.id,
                    expected_version=run.source_version,
                    outcome=outcome,
                )
            self._apply_outcome(run, outcome)
            if memory_event is not None:
                merged_events = [
                    memory_event,
                    *[
                        PlanningEventContract.model_validate(event)
                        for event in run.events
                    ],
                ]
                run.events = [
                    event.model_copy(update={"sequence": sequence}).model_dump(
                        mode="json"
                    )
                    for sequence, event in enumerate(merged_events, start=1)
                ]
        except Exception:
            await self._session.rollback()
            run = await self._session.get(AgentRun, job_id)
            if run is None:
                raise PlanningTripNotFoundError
            run.status = "failed"
            run.progress = 100
            run.error_code = "planning_failed"
            run.error_message = "LangGraph planning failed"
            run.events = [
                *run.events,
                PlanningEventContract(
                    sequence=len(run.events) + 1,
                    type="error",
                    status="failed",
                    message="规划任务失败",
                ).model_dump(mode="json"),
            ]
            run.finished_at = datetime.now(UTC)

        await self._session.flush()
        await self._session.refresh(run)
        await self._session.commit()
        return self._to_view(run)

    async def _persist_progress(
        self,
        job_id: UUID,
        state: TravelGraphState,
    ) -> None:
        run = await self._session.get(AgentRun, job_id)
        if run is None or run.status not in {"queued", "running"}:
            return
        events = state.get("events", [])
        run.status = "running"
        run.events = events
        run.progress = min(90, 15 + len(events) * 4)
        run.tool_call_count = int(state.get("tool_call_count", 0))
        run.loop_count = int(state.get("loop_count", 0))
        run.prompt_versions = [
            dict(item) for item in state.get("prompt_versions", [])
        ]
        await self._session.commit()

    async def _apply_itinerary(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
        outcome: TravelGraphOutcome,
    ) -> None:
        if outcome.draft is None:
            return
        trip = await self._versions.lock_trip(
            owner_id=owner_id,
            trip_id=trip_id,
            expected_version=expected_version,
        )
        itinerary_repository = ItineraryRepository(self._session)
        existing_days = await itinerary_repository.list_days(trip_id=trip.id)
        if existing_days:
            raise ValueError("Trip already has itinerary days")

        candidate_by_id = {
            str(candidate["provider_place_id"]): candidate
            for candidate in outcome.state.get("candidates", [])
        }
        for day_index, draft_day in enumerate(outcome.draft.days, start=1):
            day = await itinerary_repository.create_day(
                trip_id=trip.id,
                day_date=draft_day.date,
                day_index=day_index,
                theme=draft_day.theme,
            )
            for draft_stop in draft_day.stops:
                candidate = candidate_by_id.get(draft_stop.place_id, {})
                await itinerary_repository.create_stop(
                    day_id=day.id,
                    place_id=draft_stop.place_id,
                    place_name=draft_stop.place_name,
                    start_at=draft_stop.start_at,
                    duration_minutes=draft_stop.duration_minutes,
                    estimated_cost_minor=draft_stop.estimated_cost_minor,
                    location=point_from_record(candidate.get("location")),
                    source=SourceMetadata.from_record(
                        draft_stop.source.model_dump(mode="json")
                    ),
                )
        await self._versions.complete_write(model=trip, created_by=owner_id)

    async def get_job(self, *, owner_id: UUID, job_id: UUID) -> AgentRunView:
        result = await self._session.execute(
            select(AgentRun).where(
                AgentRun.id == job_id,
                AgentRun.created_by == owner_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise PlanningTripNotFoundError
        return self._to_view(run)

    def _apply_outcome(self, run: AgentRun, outcome: TravelGraphOutcome) -> None:
        run.status = outcome.status
        run.progress = 100
        run.provider = outcome.provider_name or run.provider
        run.model_name = outcome.model_name or run.model_name
        run.input_tokens = outcome.input_tokens
        run.output_tokens = outcome.output_tokens
        run.latency_ms = outcome.latency_ms
        run.estimated_cost_minor = outcome.estimated_cost_minor
        run.skills_used = [dict(item) for item in outcome.skills_used]
        run.skill_route = (
            dict(outcome.skill_route)
            if outcome.skill_route is not None
            else None
        )
        run.prompt_versions = [
            dict(item) for item in outcome.prompt_versions
        ]
        run.tool_call_count = len(outcome.tool_audits)
        run.loop_count = int(outcome.state.get("loop_count", 0))
        run.events = [event.model_dump(mode="json") for event in outcome.events]
        run.result = (
            outcome.draft.model_dump(mode="json")
            if outcome.status in {"completed", "partial"} and outcome.draft is not None
            else None
        )
        run.error_code = outcome.error_code
        run.error_message = outcome.error_message
        run.finished_at = datetime.now(UTC)
        for audit in outcome.tool_audits:
            self._session.add(
                ToolCallLog(
                    agent_run_id=run.id,
                    tool_name=audit.tool_name,
                    provider=audit.provider,
                    input_hash=audit.input_hash,
                    status=audit.status,
                    latency_ms=audit.latency_ms,
                    estimated_cost_minor=audit.estimated_cost_minor,
                    error_code=audit.error_code,
                )
            )

    @staticmethod
    def _to_view(run: AgentRun) -> AgentRunView:
        return AgentRunView(
            id=run.id,
            trip_id=run.trip_id,
            status=run.status,
            progress=run.progress,
            events=run.events,
            result=run.result,
            error_code=run.error_code,
            error_message=run.error_message,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            tool_call_count=run.tool_call_count,
            loop_count=run.loop_count,
            prompt_versions=run.prompt_versions,
        )
