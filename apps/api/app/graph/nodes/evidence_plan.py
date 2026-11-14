# 文件说明：LangGraph 节点：evidence_plan。
from uuid import UUID, uuid4

from app.evidence.draft import EvidenceDraft
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.providers.base import place_from_record


async def evidence_plan_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
) -> dict[str, object]:
    """为候选地点建立 Evidence，供 Composer 只按 ID 引用。"""
    if state.get("status") != "running":
        return {"events": graph_runtime.event_dicts()}
    graph_runtime.emit(
        "stage",
        stage="evidence_plan",
        message="正在建立候选地点 Evidence",
    )
    evidence_ids_by_place: dict[str, str] = {}
    evidence_records: list[dict[str, object]] = []
    trip_id = _trip_uuid(state.get("trip_id"))
    owner_id = graph_runtime.tool_context.owner_id or uuid4()
    try:
        for candidate in state.get("candidates", []):
            place_id = str(candidate["provider_place_id"])
            place = place_from_record(candidate)
            draft = EvidenceDraft(
                fact_type="place_fact",
                provider=place.source.provider,
                provider_record_id=place.provider_place_id,
                source_url=place.source.source_url,
                fetched_at=place.source.queried_at,
                confidence=place.source.confidence,
                freshness=place.source.freshness,
                value=candidate,
            )
            record = draft.to_record(
                owner_id=owner_id,
                trip_id=trip_id,
            )
            writer = graph_runtime.tool_context.evidence_writer
            if writer is not None:
                record = await writer.upsert(record)
            evidence_ids_by_place[place_id] = str(record.id)
            evidence_records.append(record.model_dump(mode="json"))
    except Exception:
        graph_runtime.emit(
            "error",
            status="failed",
            message="候选地点 Evidence 建立失败",
        )
        return {
            "status": "failed",
            "error_code": "evidence_plan_failed",
            "error_message": "Candidate evidence could not be prepared",
            "events": graph_runtime.event_dicts(),
        }
    graph_runtime.emit(
        "stage",
        stage="evidence_plan_complete",
        message="候选地点 Evidence 已建立",
        payload={"evidence_count": len(evidence_ids_by_place)},
    )
    return {
        "evidence_ids_by_place": evidence_ids_by_place,
        "evidence_records": evidence_records,
        "events": graph_runtime.event_dicts(),
    }


def _trip_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
