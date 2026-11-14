# 文件说明：LangGraph 节点：skill_route。
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import TripBriefContract
from app.skills.fallback import fallback_route_decision
from app.skills.manifest import SkillManifest
from app.skills.router import SkillRouter


async def skill_route_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    router: SkillRouter,
    available_skills: list[SkillManifest],
    skills_enabled: bool = True,
    router_enabled: bool = True,
) -> dict[str, object]:
    if state.get("status") != "running":
        return {"events": graph_runtime.event_dicts()}
    brief = TripBriefContract.model_validate(state["brief"])
    route_text = " ".join(
        [
            brief.destination,
            brief.origin or "",
            *brief.interests,
            *brief.lodging_preferences,
            *brief.must_visit,
            *brief.constraints,
        ]
    )
    disabled_reason = (
        "agent_skills_disabled"
        if not skills_enabled
        else "agent_skill_router_disabled"
        if not router_enabled
        else None
    )
    if disabled_reason is not None:
        decision = fallback_route_decision(disabled_reason)
        graph_runtime.emit(
            "validation",
            stage="skill_route",
            status="warning",
            message="Agent Skill 灰度开关已关闭，回退单主 Agent 流程",
            payload={"fallback_reason": disabled_reason},
        )
    else:
        try:
            decision = router.route(
                text=route_text,
                brief=brief,
                available_skills=available_skills,
            )
        except Exception as exc:
            decision = fallback_route_decision(str(exc))
            graph_runtime.emit(
                "validation",
                stage="skill_route",
                status="warning",
                message="Skill Router 不可用，回退现有行程规划链",
                payload={
                    "fallback_reason": decision.fallback_reason,
                    "repair_attempts": decision.repair_attempts,
                },
            )
        else:
            graph_runtime.emit(
                "stage",
                stage="skill_route",
                status="completed",
                message=(
                    "Skill Router 已完成选择"
                    if not decision.needs_clarification
                    else "Skill Router 需要用户澄清"
                ),
                payload={
                    "intent": decision.intent,
                    "confidence": decision.confidence,
                    "selected_skills": decision.selected_skills,
                    "budget": decision.budget.model_dump(mode="json"),
                },
            )
    route_record = decision.model_dump(mode="json")
    if decision.fallback_reason:
        return {
            "skill_route": route_record,
            "status": "running",
            "events": graph_runtime.event_dicts(),
        }
    if decision.intent == "unsupported":
        graph_runtime.emit(
            "error",
            status="failed",
            message="当前请求不在旅行规划范围内",
        )
        return {
            "skill_route": route_record,
            "status": "failed",
            "error_code": "out_of_scope",
            "error_message": "Request is outside the travel planning domain",
            "events": graph_runtime.event_dicts(),
        }
    if (
        decision.confidence < 0.7
        or decision.needs_clarification
        or decision.intent == "clarify"
    ):
        graph_runtime.emit(
            "error",
            status="failed",
            message="需要补充旅行信息后才能规划",
            payload={
                "needed_clarifications": decision.needed_clarifications,
            },
        )
        return {
            "skill_route": route_record,
            "status": "failed",
            "error_code": "clarification_required",
            "error_message": "TripBrief needs clarification",
            "events": graph_runtime.event_dicts(),
        }
    return {
        "skill_route": route_record,
        "status": "running",
        "events": graph_runtime.event_dicts(),
    }
