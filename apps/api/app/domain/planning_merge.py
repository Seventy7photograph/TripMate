# 文件说明：规划草稿字段合并与确定性优先级。
"""Merge current extraction, previous draft, and deterministic date evidence."""

from typing import Any

from app.domain.travel_dates import DateResolution
from app.schemas.planning_draft import PlanningDraft
from app.schemas.requirement import TripBriefExtraction

_LIST_FIELDS = {
    "interests",
    "transport_preferences",
    "lodging_preferences",
    "must_visit",
    "avoid",
    "constraints",
}


def merge_planning_draft(
    *,
    previous: PlanningDraft,
    extracted: TripBriefExtraction,
    date_resolution: DateResolution,
) -> PlanningDraft:
    record: dict[str, Any] = previous.model_dump()
    extracted_fields = extracted.model_fields_set

    for field_name in TripBriefExtraction.model_fields:
        if field_name not in extracted_fields:
            continue
        value = getattr(extracted, field_name)
        if field_name in _LIST_FIELDS:
            if value or not record.get(field_name):
                record[field_name] = value
            continue
        if field_name == "pace":
            if value != "balanced" or record.get("pace") in {None, "balanced"}:
                record[field_name] = value
            continue
        if field_name == "transport_strategy":
            if (
                value.strategy != "unspecified"
                or record.get("transport_strategy") is None
            ):
                record[field_name] = value.model_dump(mode="json")
            continue
        if value is not None:
            record[field_name] = (
                value.model_dump(mode="json")
                if hasattr(value, "model_dump")
                else value
            )

    if date_resolution.start_date is not None:
        record["start_date"] = date_resolution.start_date
    if date_resolution.end_date is not None:
        record["end_date"] = date_resolution.end_date

    date_context = dict(previous.date_context)
    if (
        date_resolution.start_date is not None
        or date_resolution.end_date is not None
        or date_resolution.duration_days is not None
        or date_resolution.assumptions
        or date_resolution.ambiguity_reasons
    ):
        date_context.update(
            {
                "assumptions": list(date_resolution.assumptions),
                "ambiguity_reasons": list(date_resolution.ambiguity_reasons),
                "confidence": date_resolution.confidence,
            }
        )
        if date_resolution.duration_days is not None:
            date_context["duration_days"] = date_resolution.duration_days
    record["date_context"] = date_context

    return PlanningDraft.model_validate(record)
