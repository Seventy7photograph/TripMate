# 文件说明：LangGraph 节点：evidence_verify。
from app.evidence.models import EvidenceRecord
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import ItineraryDraftContract
from app.services.evidence_validation_service import EvidenceValidationService


async def evidence_verify_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
) -> dict[str, object]:
    if state.get("status") != "completed" or state.get("draft") is None:
        return {"events": graph_runtime.event_dicts()}
    graph_runtime.emit(
        "stage",
        stage="evidence_verify",
        message="正在核验行程事实与 Evidence",
    )
    draft = ItineraryDraftContract.model_validate(state["draft"])
    records = [
        EvidenceRecord.model_validate(item)
        for item in state.get("evidence_records", [])
    ]
    report = EvidenceValidationService().validate(draft, records=records)
    validation_issues = report.as_validation_issues()
    merged_issues = [
        *draft.validation_summary,
        *validation_issues,
    ]
    updated_draft = draft.model_copy(
        update={"validation_summary": merged_issues}
    )
    has_blocking_issue = any(
        issue.severity in {"error", "fatal"}
        for issue in validation_issues
    )
    graph_runtime.emit(
        "validation",
        stage="evidence_verify",
        status="warning" if validation_issues else "passed",
        message=(
            f"Evidence 核验发现 {len(validation_issues)} 个问题"
            if validation_issues
            else "Evidence 核验通过"
        ),
        payload={
            "verified_count": report.verified_count,
            "issue_codes": [issue.code for issue in report.issues],
        },
    )
    return {
        "status": "partial" if has_blocking_issue else "completed",
        "draft": updated_draft.model_dump(mode="json"),
        "issues": [
            issue.model_dump(mode="json")
            for issue in validation_issues
        ],
        "evidence_issues": [
            issue.model_dump(mode="json")
            for issue in report.issues
        ],
        "events": graph_runtime.event_dicts(),
    }
