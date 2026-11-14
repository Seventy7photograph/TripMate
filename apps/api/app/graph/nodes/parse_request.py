# 文件说明：LangGraph 节点：parse_request。
from pydantic import ValidationError

from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.schemas.ai import TripBriefContract


async def parse_request_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
) -> dict[str, object]:
    graph_runtime.emit("stage", stage="planning", message="正在校验已确认的旅行需求")
    if not state.get("brief_confirmed", False):
        graph_runtime.emit(
            "error",
            status="failed",
            message="旅行需求尚未确认，不能启动生成",
        )
        return {
            "status": "failed",
            "error_code": "brief_not_confirmed",
            "error_message": "TripBrief is not confirmed",
            "events": graph_runtime.event_dicts(),
        }
    if graph_runtime.is_expired():
        graph_runtime.emit("error", status="failed", message="规划任务已超时")
        return {
            "status": "failed",
            "error_code": "graph_timeout",
            "error_message": "Graph deadline exceeded",
            "events": graph_runtime.event_dicts(),
        }
    try:
        TripBriefContract.model_validate(state.get("brief"))
    except ValidationError:
        graph_runtime.emit("error", status="failed", message="旅行需求结构无效")
        return {
            "status": "failed",
            "error_code": "invalid_brief",
            "error_message": "TripBrief validation failed",
            "events": graph_runtime.event_dicts(),
        }
    return {"status": "running", "events": graph_runtime.event_dicts()}
