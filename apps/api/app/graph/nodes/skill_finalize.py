# 文件说明：LangGraph 节点：基于最终草案执行路线与预算 Skill。
import json
from dataclasses import replace
from typing import cast

from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import (
    ItineraryDraftContract,
    TransportPlanContract,
    ValidationIssueContract,
)
from app.skills.runtime import SkillRuntime

_POST_COMPOSE_SKILLS = ("route-optimization", "budget-optimization")


async def skill_finalize_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    skill_runtime: SkillRuntime | None,
) -> dict[str, object]:
    if (
        state.get("status") != "completed"
        or state.get("draft") is None
        or skill_runtime is None
    ):
        return {"events": graph_runtime.event_dicts()}
    route = state.get("skill_route") or {}
    selected = {
        str(item)
        for item in cast(list[object], route.get("selected_skills", []))
    }
    selected_post = [
        name for name in _POST_COMPOSE_SKILLS if name in selected
    ]
    if not selected_post:
        return {"events": graph_runtime.event_dicts()}

    draft = ItineraryDraftContract.model_validate(state["draft"])
    brief = dict(state["brief"])
    candidates = list(state.get("candidates", []))
    skill_results = dict(state.get("skill_results", {}))
    skills_used = [dict(item) for item in state.get("skills_used", [])]
    skill_errors = dict(state.get("skill_errors", {}))
    budget = cast(dict[str, object], route.get("budget") or {})
    allowed_tools = {
        str(item) for item in cast(list[object], budget.get("allowed_tools", []))
    }
    allowed_mcp = {
        str(item)
        for item in cast(
            list[object],
            budget.get("allowed_mcp_connectors", []),
        )
    }
    remaining_calls = int(str(budget.get("max_tool_calls", 12)))
    remaining_tokens = int(str(budget.get("max_tokens", 32_000)))

    for skill_name in selected_post:
        payload = _payload_for_skill(
            skill_name,
            draft=draft,
            brief=brief,
            candidates=candidates,
        )
        if payload is None:
            continue
        graph_runtime.emit(
            "stage",
            stage="skill_finalize",
            status="running",
            message=f"正在基于草案执行 Skill：{skill_name}",
        )
        try:
            manifest = skill_runtime.selected_manifest(skill_name)
        except LookupError:
            skill_errors[skill_name] = "LookupError:skill_disabled"
            continue
        try:
            scoped_context = replace(
                skill_runtime.tool_context,
                runner=skill_runtime.tool_context.runner.scoped(
                    max_calls=min(
                        manifest.max_tool_calls,
                        remaining_calls,
                    )
                ),
                allowed_tools=(
                    set(manifest.allowed_tools) & allowed_tools
                    if allowed_tools
                    else set(manifest.allowed_tools)
                ),
                allowed_mcp_connectors=(
                    set(manifest.allowed_mcp_connectors)
                    & allowed_mcp
                    & set(skill_runtime.tool_context.allowed_mcp_connectors)
                ),
            )
            result = await skill_runtime.execute(
                skill_name,
                payload,
                tool_context=scoped_context,
                max_tokens=remaining_tokens,
            )
        except Exception as exc:
            fallback = str(
                getattr(exc, "fallback", manifest.fallback)
            )
            skill_errors[skill_name] = (
                f"{type(exc).__name__}:{fallback}"
            )
            graph_runtime.emit(
                "validation",
                stage="skill_finalize",
                status="warning",
                message=f"Skill 执行失败并降级：{skill_name}",
                payload={"error": type(exc).__name__},
            )
            continue
        remaining_calls = max(0, remaining_calls - result.tool_calls)
        remaining_tokens = max(
            0,
            remaining_tokens
            - max(
                1,
                (
                    len(
                        json.dumps(
                            result.output.model_dump(mode="json"),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
                    + 1
                )
                // 2,
            ),
        )
        skill_results[skill_name] = result.output.model_dump(mode="json")
        skills_used.append(
            {
                "name": result.skill_name,
                "version": result.version,
                "status": result.status,
            }
        )
        if skill_name == "route-optimization":
            draft = _apply_route_result(draft, result.output.model_dump())
        elif skill_name == "budget-optimization":
            draft = _apply_budget_result(draft, result.output.model_dump())
        graph_runtime.emit(
            "stage",
            stage="skill_finalize",
            status="completed",
            message=f"Skill 执行完成：{skill_name}",
            payload={
                "version": result.version,
                "tool_calls": result.tool_calls,
            },
        )

    return {
        "draft": draft.model_dump(mode="json"),
        "skill_results": skill_results,
        "skill_errors": skill_errors,
        "skills_used": skills_used,
        "tool_call_count": graph_runtime.tools.call_count,
        "events": graph_runtime.event_dicts(),
    }


def _payload_for_skill(
    skill_name: str,
    *,
    draft: ItineraryDraftContract,
    brief: dict[str, object],
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    if skill_name == "budget-optimization":
        return {
            "stop_costs_minor": [
                stop.estimated_cost_minor
                for day in draft.days
                for stop in day.stops
            ],
            "budget_minor": brief.get("budget_minor"),
        }
    if skill_name != "route-optimization":
        return None
    candidate_by_id = {
        str(candidate["provider_place_id"]): candidate
        for candidate in candidates
    }
    points: list[dict[str, object]] = []
    for day in draft.days:
        for stop in day.stops:
            candidate = candidate_by_id.get(stop.place_id)
            if candidate is None:
                continue
            location = candidate.get("location")
            if isinstance(location, dict):
                points.append(dict(location))
            if len(points) >= 2:
                break
        if len(points) >= 2:
            break
    if len(points) < 2:
        return None
    preferences = cast(list[object], brief.get("transport_preferences", []))
    return {
        "origin": points[0],
        "destination": points[1],
        "mode": _route_mode(preferences),
        "city": brief.get("destination"),
    }


def _route_mode(preferences: list[object]) -> str:
    aliases = {
        "步行": "walking",
        "walking": "walking",
        "自驾": "driving",
        "driving": "driving",
        "骑行": "bicycling",
        "bicycling": "bicycling",
        "公交": "bus",
        "bus": "bus",
        "地铁": "subway",
        "subway": "subway",
        "飞机": "flight",
        "flight": "flight",
    }
    for preference in preferences:
        text = str(preference)
        for label, mode in aliases.items():
            if label in text:
                return mode
    return "walking"


def _apply_route_result(
    draft: ItineraryDraftContract,
    payload: dict[str, object],
) -> ItineraryDraftContract:
    duration_s = payload.get("duration_s")
    distance_m = payload.get("distance_m")
    transport = TransportPlanContract(
        mode="provider_route",
        duration_minutes=(
            max(1, int(str(duration_s)) // 60)
            if duration_s is not None
            else None
        ),
        distance_m=(
            int(str(distance_m)) if distance_m is not None else None
        ),
        summary="基于最终草案地点计算的 Provider 路线",
    )
    days = list(draft.days)
    if days:
        days[0] = days[0].model_copy(
            update={"transport": [transport]}
        )
    return draft.model_copy(update={"days": days})


def _apply_budget_result(
    draft: ItineraryDraftContract,
    payload: dict[str, object],
) -> ItineraryDraftContract:
    if bool(payload.get("within_budget", True)):
        return draft
    return draft.model_copy(
        update={
            "validation_summary": [
                *draft.validation_summary,
                ValidationIssueContract(
                    code="budget_exceeded",
                    severity="warning",
                    path="budget",
                    message="最终草案预计费用超过旅行预算",
                ),
            ]
        }
    )
