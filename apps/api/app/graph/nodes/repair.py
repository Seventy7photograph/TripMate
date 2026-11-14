# 文件说明：LangGraph 节点：repair。
from datetime import datetime, time, timedelta

from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.providers.base import point_from_record
from app.schemas.ai import (
    DayPlanContract,
    ItineraryDraftContract,
    ItineraryStopContract,
    TripBriefContract,
)


def _locked_place_ids(
    brief: TripBriefContract,
    candidates: list[dict[str, object]],
) -> set[str]:
    locked: set[str] = set()
    for candidate in candidates:
        name = str(candidate.get("name") or "")
        if any(
            visit in name or name in visit
            for visit in brief.must_visit
            if visit and name
        ):
            locked.add(str(candidate["provider_place_id"]))
    return locked


def repair_itinerary(
    draft: ItineraryDraftContract,
    *,
    brief: TripBriefContract,
    candidates: list[dict[str, object]],
) -> tuple[ItineraryDraftContract, int]:
    candidate_by_id = {
        str(candidate["provider_place_id"]): candidate
        for candidate in candidates
    }
    locked = _locked_place_ids(brief, candidates)
    changed = 0
    repaired_days: list[DayPlanContract] = []

    for day in draft.days:
        stops = sorted(day.stops, key=lambda item: item.start_at)
        repaired_stops: list[ItineraryStopContract] = []
        previous_end: datetime | None = None

        for stop in stops:
            candidate = candidate_by_id.get(stop.place_id)
            has_location = (
                candidate is not None
                and point_from_record(candidate.get("location")) is not None
            )
            if not has_location and stop.place_id not in locked:
                changed += 1
                continue

            next_stop = stop
            if stop.place_id not in locked:
                next_start = stop.start_at
                if next_start.date() != day.date:
                    next_start = datetime.combine(day.date, time(9, 0))
                    changed += 1
                if previous_end is not None and next_start < previous_end:
                    next_start = previous_end + timedelta(minutes=15)
                    changed += 1
                if next_start != stop.start_at:
                    next_stop = stop.model_copy(update={"start_at": next_start})

            repaired_stops.append(next_stop)
            candidate_end = next_stop.start_at + timedelta(
                minutes=next_stop.duration_minutes
            )
            previous_end = (
                max(previous_end, candidate_end)
                if previous_end is not None
                else candidate_end
            )

        if brief.budget_minor is not None:
            while (
                sum(item.estimated_cost_minor for item in repaired_stops)
                > brief.budget_minor
            ):
                optional_index = next(
                    (
                        index
                        for index in range(len(repaired_stops) - 1, -1, -1)
                        if repaired_stops[index].place_id not in locked
                    ),
                    None,
                )
                if optional_index is None:
                    break
                repaired_stops.pop(optional_index)
                changed += 1

        repaired_days.append(
            day.model_copy(update={"stops": repaired_stops})
        )

    return (
        draft.model_copy(
            update={
                "days": repaired_days,
                "validation_summary": [],
            }
        ),
        changed,
    )


async def repair_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
) -> dict[str, object]:
    draft_payload = state.get("draft")
    if draft_payload is None:
        return {
            "status": "failed",
            "error_code": "invalid_schema",
            "error_message": "Draft is required for repair",
            "events": graph_runtime.event_dicts(),
        }
    brief = TripBriefContract.model_validate(state["brief"])
    draft = ItineraryDraftContract.model_validate(draft_payload)
    repaired, changed = repair_itinerary(
        draft,
        brief=brief,
        candidates=state.get("candidates", []),
    )
    graph_runtime.emit(
        "stage",
        stage="repair",
        status="running",
        message="正在修复行程冲突",
        payload={"changed_stops": changed},
    )
    return {
        "status": "running",
        "draft": repaired.model_dump(mode="json"),
        "issues": [],
        "events": graph_runtime.event_dicts(),
    }
