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
from app.evidence.service import EvidenceService
from app.graph.state import TravelGraphState
from app.graph.travel_graph import TravelGraph, TravelGraphOutcome, create_travel_graph
from app.models.agent_run import AgentRun
from app.models.tool_call_log import ToolCallLog
from app.providers.base import point_from_record
from app.queue.planning_queue import PlanningQueue, create_planning_queue
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.ai import PlanningEventContract, TripBriefContract
from app.services.cost_guard import CostGuard, settled_cost_minor
from app.services.feature_service import FeatureDisabledError, FeatureFlagService
from app.services.provider_health_service import ProviderHealthService
from app.services.version_service import VersionService, VersionTripNotFoundError
from app.skills.runtime import SkillRuntime, build_skill_runtime
from app.skills.state_service import SkillStateService
from app.tools.memory_tools import AuthorizedMemoryOutput


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
        self._skill_runtime: SkillRuntime | None = None

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
            requested_cost_minor=self._settings.planning_max_cost_minor,
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
            estimated_cost_minor=self._settings.planning_max_cost_minor,
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
        try:
            await self._queue.enqueue(run.id)
        except Exception:
            await self._fail_enqueue_if_unstarted(run.id)
            raise

        if self._queue.is_inline:
            return await self.run_job(run.id)
        return self._to_view(run)

    async def run_job(self, job_id: UUID) -> AgentRunView:
        try:
            return await self._run_job(job_id)
        except Exception as exc:
            await self._session.rollback()
            run = await self._session.get(AgentRun, job_id)
            if run is not None and run.status == "running":
                await self._fail_run(
                    run,
                    error_code="planning_setup_failed",
                    error_message=str(exc)[:500] or "Planning setup failed",
                    estimated_cost_minor=0,
                )
            raise
        finally:
            runtime = self._skill_runtime
            self._skill_runtime = None
            if runtime is not None:
                await runtime.close()

    async def _run_job(self, job_id: UUID) -> AgentRunView:
        # 已完成任务直接返回，避免 Worker 重启后重复生成。
        run = await self._session.get(AgentRun, job_id)
        if run is None:
            raise PlanningTripNotFoundError
        if run.status in {"completed", "failed"}:
            return self._to_view(run)
        try:
            await self._features.require_all(
                ["ai_planning", "llm_provider", "map_provider"]
            )
        except FeatureDisabledError as exc:
            return await self._fail_run(
                run,
                error_code="feature_disabled",
                error_message=f"Planning feature disabled: {exc.key}",
                estimated_cost_minor=0,
            )
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
        memory_query = " ".join(
            [
                trip.brief.destination,
                trip.brief.origin or "",
                *trip.brief.interests,
                *trip.brief.lodging_preferences,
            ]
        )
        skill_runtime = await build_skill_runtime(
            session=self._session,
            settings=self._settings,
            owner_id=run.created_by,
            trip_id=trip.id,
        )
        self._skill_runtime = skill_runtime
        skills_enabled = await self._features.is_enabled(
            "agent_skills_enabled"
        )
        router_enabled = await self._features.is_enabled(
            "agent_skill_router_enabled"
        )
        available_skills = (
            await SkillStateService(self._session).enabled_manifests(
                skill_runtime.registry
            )
            if skills_enabled and router_enabled
            else []
        )
        skill_state_snapshot = sorted(
            [skill.name, skill.version] for skill in available_skills
        )
        stored_snapshot = (
            run.skill_route.get("skill_state_snapshot")
            if isinstance(run.skill_route, dict)
            else None
        )
        if stored_snapshot is not None and stored_snapshot != skill_state_snapshot:
            return await self._fail_run(
                run,
                error_code="skill_state_changed",
                error_message="Skill state changed since planning started",
                estimated_cost_minor=0,
            )
        if stored_snapshot is None:
            run.skill_route = {
                "skill_state_snapshot": skill_state_snapshot,
            }
            await self._session.commit()
        skill_runtime.selected_manifests = {
            skill.name: skill for skill in available_skills
        }
        memory_skills_used: list[dict[str, object]] = []
        memory_event: PlanningEventContract | None = None
        try:
            if (
                skills_enabled
                and any(
                    skill.name == "travel-memory"
                    for skill in available_skills
                )
            ):
                memory_result = await skill_runtime.execute(
                    "travel-memory",
                    {"query": memory_query, "limit": 8},
                )
                memory_output = AuthorizedMemoryOutput.model_validate(
                    memory_result.output
                )
                memory_constraints = [
                    item.content for item in memory_output.items
                ]
                memory_skills_used.append(
                    {
                        "name": memory_result.skill_name,
                        "version": memory_result.version,
                        "status": memory_result.status,
                    }
                )
            else:
                from app.services.memory_service import MemoryService

                memory_constraints = await MemoryService(
                    self._session
                ).retrieval_constraints(
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
            outcome = await self._graph.run(
                trip_id=str(trip.id),
                version=run.source_version,
                brief=contract,
                brief_confirmed=True,
                thread_id=str(run.id),
                checkpointer=self._checkpointer,
                resume=was_started,
                owner_id=run.created_by,
                evidence_writer=EvidenceService(self._session),
                available_skills=available_skills,
                skills_enabled=skills_enabled,
                router_enabled=router_enabled,
                skill_runtime=skill_runtime,
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
            run.skills_used = [
                *memory_skills_used,
                *run.skills_used,
            ]
            run.tool_call_count = (
                len(outcome.tool_audits)
                + len(skill_runtime.tool_context.runner.audits)
            )
            for audit in skill_runtime.tool_context.runner.audits:
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
            provider_health = ProviderHealthService(self._session)
            for audit in [
                *outcome.tool_audits,
                *skill_runtime.tool_context.runner.audits,
            ]:
                await provider_health.record_audit(audit)
            await provider_health.record_llm(
                provider_name=run.provider,
                status=(
                    "healthy"
                    if run.status in {"completed", "partial"}
                    else "degraded"
                ),
                latency_ms=run.latency_ms,
                model_name=run.model_name,
            )
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
            await ProviderHealthService(self._session).record_llm(
                provider_name=run.provider,
                status="degraded",
                latency_ms=int(
                    (
                        run.finished_at
                        - (run.started_at or run.finished_at)
                    ).total_seconds()
                    * 1_000
                ),
                model_name=run.model_name,
                error_code=run.error_code,
            )

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
            # 版本锁已保存修改前快照；显式 apply 时替换现有逐日行程。
            await itinerary_repository.delete_days_for_trip(trip_id=trip.id)

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
        run.estimated_cost_minor = settled_cost_minor(
            reserved=run.estimated_cost_minor,
            reported=outcome.estimated_cost_minor,
            provider=outcome.provider_name or self._graph.provider_name,
        )
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

    async def _fail_run(
        self,
        run: AgentRun,
        *,
        error_code: str,
        error_message: str,
        estimated_cost_minor: int,
    ) -> AgentRunView:
        run.status = "failed"
        run.progress = 100
        run.error_code = error_code
        run.error_message = error_message
        run.estimated_cost_minor = estimated_cost_minor
        run.finished_at = datetime.now(UTC)
        run.events = [
            *run.events,
            PlanningEventContract(
                sequence=len(run.events) + 1,
                type="error",
                status="failed",
                message=error_message,
            ).model_dump(mode="json"),
        ]
        await self._session.commit()
        return self._to_view(run)

    async def _fail_enqueue_if_unstarted(self, job_id: UUID) -> None:
        await self._session.rollback()
        result = await self._session.execute(
            select(AgentRun)
            .where(AgentRun.id == job_id)
            .with_for_update()
        )
        run = result.scalar_one_or_none()
        if (
            run is None
            or run.status != "queued"
            or run.started_at is not None
        ):
            return
        await self._fail_run(
            run,
            error_code="queue_enqueue_failed",
            error_message="Planning queue enqueue failed",
            estimated_cost_minor=0,
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
