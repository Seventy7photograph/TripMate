# 文件说明：LangGraph 节点：persist_plan。
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState


async def persist_plan_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
) -> dict[str, object]:
    if state.get("status") in {"completed", "partial"} and state.get("draft") is not None:
        is_partial = state.get("status") == "partial"
        graph_runtime.emit(
            "complete",
            status="partial" if is_partial else "completed",
            message=(
                "已返回部分行程结果，仍有未解决问题"
                if is_partial
                else "AI 行程草案已生成，等待 service 持久化"
            ),
        )
        return {
            "status": "partial" if is_partial else "completed",
            "events": graph_runtime.event_dicts(),
        }
    graph_runtime.emit(
        "error",
        status="failed",
        message=state.get("error_message") or "规划任务失败",
    )
    return {
        "status": "failed",
        "error_code": state.get("error_code") or "planning_failed",
        "events": graph_runtime.event_dicts(),
    }
