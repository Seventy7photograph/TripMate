# 文件说明：LangGraph 节点：evaluator。
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import (
    ItineraryDraftContract,
    TripBriefContract,
    ValidationIssueContract,
)
from app.services.validation.budget_validator import validate_budget
from app.services.validation.route_validator import validate_routes
from app.services.validation.source_validator import validate_sources
from app.services.validation.time_validator import validate_time
from app.tools.base import ToolLimitExceeded, ToolTimeoutError
from app.tools.budget_tools import BudgetTool
from app.tools.route_tools import RouteTool

_REPAIRABLE_CODES = {
    "unknown_place",
    "missing_coordinates",
    "route_unavailable",
    "time_conflict",
    "commute_too_long",
    "budget_exceeded",
    "invalid_schema",
}


async def evaluator_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    route_tool: RouteTool,
    budget_tool: BudgetTool,
    max_repairs: int,
) -> dict[str, object]:
    draft_payload = state.get("draft")
    if draft_payload is None:
        graph_runtime.emit("error", status="failed", message="没有可校验的行程草案")
        return {
            "status": "failed",
            "error_code": "invalid_schema",
            "error_message": "Draft is required",
            "events": graph_runtime.event_dicts(),
        }
    draft = ItineraryDraftContract.model_validate(draft_payload)
    brief = TripBriefContract.model_validate(state["brief"])
    evidence_issues = [
        ValidationIssueContract.model_validate(issue)
        for issue in state.get("issues", [])
    ]
    audit_start = len(graph_runtime.tools.audits)
    try:
        issues = [
            *evidence_issues,
            *validate_time(draft),
            *validate_sources(draft),
            *await validate_routes(
                draft,
                candidates=state.get("candidates", []),
                route_lookup=route_tool,
            ),
            *await validate_budget(
                draft,
                brief=brief,
                budget_lookup=budget_tool,
            ),
        ]
    except ToolLimitExceeded:
        graph_runtime.emit("error", status="failed", message="校验工具达到调用上限")
        return {
            "status": "failed",
            "error_code": "tool_limit_exceeded",
            "error_message": "Tool limit exceeded during evaluation",
            "events": graph_runtime.event_dicts(),
        }
    except ToolTimeoutError:
        graph_runtime.emit("error", status="failed", message="校验工具超时")
        return {
            "status": "failed",
            "error_code": "graph_timeout",
            "error_message": "Tool timeout during evaluation",
            "events": graph_runtime.event_dicts(),
        }

    for audit in graph_runtime.tools.audits[audit_start:]:
        graph_runtime.emit(
            "tool_call",
            tool_name=audit.tool_name,
            provider=audit.provider,
            status=audit.status,
            message="确定性校验工具执行完成",
            payload={
                "latency_ms": audit.latency_ms,
                "error_code": audit.error_code,
            },
        )

    draft.validation_summary = issues
    actionable = [
        issue
        for issue in issues
        if (
            issue.code == "budget_exceeded"
            or (
                issue.code in _REPAIRABLE_CODES
                and issue.severity in {"error", "fatal"}
            )
        )
    ]
    loop_count = int(state.get("loop_count", 0))
    payload = {
        "issue_count": len(issues),
        "repairable_count": len(actionable),
        "evaluation_round": loop_count + 1,
        "tool_call_count": graph_runtime.tools.call_count,
        "elapsed_ms": graph_runtime.elapsed_ms,
    }
    graph_runtime.emit(
        "validation",
        status="passed" if not actionable else "warning",
        message=(
            "行程规则校验通过"
            if not actionable
            else f"发现 {len(actionable)} 个可修复问题"
        ),
        payload=payload,
    )

    if actionable and loop_count < max_repairs:
        return {
            "status": "repairing",
            "draft": draft.model_dump(mode="json"),
            "issues": [issue.model_dump(mode="json") for issue in issues],
            "loop_count": loop_count + 1,
            "tool_call_count": graph_runtime.tools.call_count,
            "events": graph_runtime.event_dicts(),
        }
    if actionable:
        graph_runtime.emit(
            "validation",
            status="partial",
            message="达到修复上限，返回部分结果和未解决问题",
            payload=payload,
        )
        return {
            "status": "partial",
            "draft": draft.model_dump(mode="json"),
            "issues": [issue.model_dump(mode="json") for issue in issues],
            "loop_count": loop_count,
            "tool_call_count": graph_runtime.tools.call_count,
            "events": graph_runtime.event_dicts(),
        }
    return {
        "status": "completed",
        "draft": draft.model_dump(mode="json"),
        "issues": [issue.model_dump(mode="json") for issue in issues],
        "loop_count": loop_count,
        "tool_call_count": graph_runtime.tools.call_count,
        "events": graph_runtime.event_dicts(),
    }
