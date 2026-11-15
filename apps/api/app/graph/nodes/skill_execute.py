# 文件说明：LangGraph 节点：执行 Router 选中的生产 Skill 并写入审计。
import json
from dataclasses import replace
from datetime import timedelta
from typing import cast
from uuid import UUID

from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import TripBriefContract
from app.skills.runtime import SkillRuntime

_MODE_ALIASES = {
    "walking": "walking",
    "步行": "walking",
    "driving": "driving",
    "自驾": "driving",
    "bicycling": "bicycling",
    "骑行": "bicycling",
    "bus": "bus",
    "公交": "bus",
    "subway": "subway",
    "地铁": "subway",
    "flight": "flight",
    "飞机": "flight",
}
_POST_COMPOSE_SKILLS = {"route-optimization", "budget-optimization"}


async def skill_execute_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    skill_runtime: SkillRuntime | None,
) -> dict[str, object]:
    if state.get("status") != "running" or skill_runtime is None:
        return {"events": graph_runtime.event_dicts()}

    route = state.get("skill_route") or {}
    selected_skills = [
        str(item)
        for item in cast(list[object], route.get("selected_skills", []))
        if str(item) not in _POST_COMPOSE_SKILLS
    ]
    if not selected_skills:
        return {
            "skills_used": list(state.get("skills_used", [])),
            "skill_results": dict(state.get("skill_results", {})),
            "events": graph_runtime.event_dicts(),
        }

    brief = TripBriefContract.model_validate(state["brief"])
    candidates = list(state.get("candidates", []))
    skill_results = dict(state.get("skill_results", {}))
    skills_used = [dict(item) for item in state.get("skills_used", [])]
    skill_errors = dict(state.get("skill_errors", {}))
    budget = cast(dict[str, object], route.get("budget") or {})
    route_allowed_tools = {
        str(item) for item in cast(list[object], budget.get("allowed_tools", []))
    }
    route_allowed_mcp = {
        str(item)
        for item in cast(
            list[object],
            budget.get("allowed_mcp_connectors", []),
        )
    }
    remaining_calls = int(str(budget.get("max_tool_calls", 12)))
    remaining_tokens = int(str(budget.get("max_tokens", 32_000)))

    for skill_name in selected_skills:
        payload = _skill_payload(
            skill_name,
            brief=brief,
            candidates=candidates,
        )
        if payload is None:
            continue
        graph_runtime.emit(
            "stage",
            stage="skill_execute",
            status="running",
            message=f"正在执行 Skill：{skill_name}",
        )
        try:
            manifest = skill_runtime.manifest(skill_name)
            scoped_context = replace(
                skill_runtime.tool_context,
                runner=skill_runtime.tool_context.runner.scoped(
                    max_calls=min(
                        manifest.max_tool_calls,
                        remaining_calls,
                    )
                ),
                allowed_tools=(
                    set(manifest.allowed_tools) & route_allowed_tools
                    if route_allowed_tools
                    else set(manifest.allowed_tools)
                ),
                allowed_mcp_connectors=(
                    set(manifest.allowed_mcp_connectors)
                    & route_allowed_mcp
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
            manifest = skill_runtime.manifest(skill_name)
            fallback = str(
                getattr(exc, "fallback", manifest.fallback)
            )
            skill_errors[skill_name] = (
                f"{type(exc).__name__}:{fallback}"
            )
            graph_runtime.emit(
                "validation",
                stage="skill_execute",
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
        if skill_name == "destination-research":
            discovered = result.output.model_dump(mode="json").get("places", [])
            if isinstance(discovered, list):
                candidates = _merge_candidates(candidates, discovered)
        skills_used.append(
            {
                "name": result.skill_name,
                "version": result.version,
                "status": result.status,
            }
        )
        graph_runtime.emit(
            "stage",
            stage="skill_execute",
            status="completed",
            message=f"Skill 执行完成：{skill_name}",
            payload={
                "version": result.version,
                "tool_calls": result.tool_calls,
            },
        )

    evidence_records = [
        dict(item) for item in state.get("evidence_records", [])
    ]
    evidence_ids = _evidence_ids(skill_results)
    evidence_writer = skill_runtime.tool_context.evidence_writer
    reader = getattr(evidence_writer, "list_for_owner", None)
    if (
        evidence_ids
        and skill_runtime.tool_context.owner_id is not None
        and callable(reader)
    ):
        loaded = await reader(
            owner_id=skill_runtime.tool_context.owner_id,
            evidence_ids=evidence_ids,
        )
        evidence_records.extend(
            record.model_dump(mode="json") for record in loaded
        )

    return {
        "skill_results": skill_results,
        "skill_errors": skill_errors,
        "skills_used": skills_used,
        "candidates": candidates,
        "evidence_records": _deduplicate_records(evidence_records),
        "tool_call_count": graph_runtime.tools.call_count,
        "events": graph_runtime.event_dicts(),
    }


def _skill_payload(
    skill_name: str,
    *,
    brief: TripBriefContract,
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    if skill_name == "destination-research":
        query = brief.must_visit[0] if brief.must_visit else brief.destination
        return {
            "query": query,
            "city": brief.destination,
            "limit": 5,
        }
    if skill_name == "route-optimization":
        points = _candidate_points(candidates)
        if len(points) < 2:
            return None
        mode = _route_mode(brief.transport_preferences)
        return {
            "origin": points[0],
            "destination": points[1],
            "mode": mode,
            "city": brief.destination,
        }
    if skill_name == "budget-optimization":
        return {
            "stop_costs_minor": [],
            "budget_minor": brief.budget_minor,
        }
    if skill_name == "weather-and-clothing":
        return {
            "city": brief.destination,
            "date": brief.start_date.isoformat(),
        }
    if skill_name == "food-planning":
        return {
            "meal": "lunch",
            "city": brief.destination,
            "dietary": brief.constraints,
            "date": brief.start_date.isoformat(),
            "limit": 2,
        }
    if skill_name == "lodging-area-selection":
        return {
            "city": brief.destination,
            "preferences": brief.lodging_preferences,
            "budget_minor_per_night": (
                brief.budget_minor // _trip_nights(brief)
                if brief.budget_minor is not None
                else None
            ),
            "limit": 2,
        }
    if skill_name == "safety-briefing":
        return {
            "dates": _trip_dates(brief),
            "party": _party_constraints(brief),
            "city": brief.destination,
        }
    return None


def _candidate_points(
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    for candidate in candidates:
        location = candidate.get("location")
        if not isinstance(location, dict):
            continue
        longitude = location.get("longitude")
        latitude = location.get("latitude")
        coordinate_system = location.get("coordinate_system")
        if (
            isinstance(longitude, (int, float))
            and isinstance(latitude, (int, float))
            and coordinate_system in {"GCJ-02", "WGS84"}
        ):
            points.append(
                {
                    "longitude": longitude,
                    "latitude": latitude,
                    "coordinate_system": coordinate_system,
                }
            )
    return points


def _route_mode(preferences: list[str]) -> str:
    for preference in preferences:
        mode = _MODE_ALIASES.get(preference)
        if mode is not None:
            return mode
        for label, normalized in _MODE_ALIASES.items():
            if label in preference:
                return normalized
    return "walking"


def _trip_dates(brief: TripBriefContract) -> list[str]:
    current = brief.start_date
    dates: list[str] = []
    while current <= brief.end_date and len(dates) < 7:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _trip_nights(brief: TripBriefContract) -> int:
    return max(1, (brief.end_date - brief.start_date).days)


def _party_constraints(brief: TripBriefContract) -> list[str]:
    searchable = " ".join(
        [
            *brief.constraints,
            *brief.interests,
            *brief.avoid,
        ]
    )
    party: list[str] = []
    labels = {
        "老人": "older_adult",
        "儿童": "child",
        "孩子": "child",
        "孕期": "pregnant",
        "孕妇": "pregnant",
        "慢性病": "chronic_condition",
    }
    for label, value in labels.items():
        if label in searchable:
            party.append(value)
    return party


def _evidence_ids(value: object) -> set[UUID]:
    found: set[UUID] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "evidence_ids" or key == "evidence_id":
                found.update(_uuid_values(item))
            else:
                found.update(_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_evidence_ids(item))
    return found


def _uuid_values(value: object) -> set[UUID]:
    values = value if isinstance(value, list) else [value]
    found: set[UUID] = set()
    for item in values:
        try:
            found.add(UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return found


def _deduplicate_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for record in records:
        record_id = str(record.get("id", ""))
        if record_id:
            by_id[record_id] = record
    return list(by_id.values())


def _merge_candidates(
    current: list[dict[str, object]],
    discovered: list[object],
) -> list[dict[str, object]]:
    by_id = {
        str(candidate.get("provider_place_id")): candidate
        for candidate in current
    }
    for item in discovered:
        if not isinstance(item, dict):
            continue
        place_id = str(item.get("provider_place_id", ""))
        if place_id:
            by_id[place_id] = item
    return list(by_id.values())
