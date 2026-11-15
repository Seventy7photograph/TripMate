# 文件说明：LangGraph 节点：research。
from app.agents.research_planner import ResearchPlanner
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.providers.base import ProviderError
from app.providers.llm.base import (
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.schemas.ai import TripBriefContract
from app.tools.base import ToolDeadlineExceeded, ToolLimitExceeded, ToolTimeoutError
from app.tools.place_tools import PlaceTool


async def research_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    place_tool: PlaceTool,
    research_planner: ResearchPlanner,
) -> dict[str, object]:
    brief = TripBriefContract.model_validate(state["brief"])
    graph_runtime.emit("stage", stage="research", message="正在选择地点检索工具")
    candidates: dict[str, dict[str, object]] = {}
    failed_queries = 0
    try:
        plan = await research_planner.plan(
            brief=brief,
            tools=graph_runtime.tool_registry.openai_schemas({"search_places"}),
        )
        if not plan.queries:
            return _failed(
                graph_runtime,
                error_code="no_research_queries",
                message="模型没有选择合法的地点检索工具",
                tool_call_count=graph_runtime.tools.call_count,
            )
        graph_runtime.emit(
            "stage",
            stage="research",
            message="正在执行地点检索",
            payload={"query_count": len(plan.queries)},
        )
        for query in plan.queries:
            try:
                output = await place_tool.search(query)
            except ProviderError:
                failed_queries += 1
                graph_runtime.emit(
                    "tool_call",
                    tool_name=place_tool.name,
                    provider=place_tool.provider_name,
                    status="error",
                    message=f"地点检索失败：{query.keyword}",
                )
                continue
            graph_runtime.emit(
                "tool_call",
                tool_name=place_tool.name,
                provider=place_tool.provider_name,
                status="success",
                message=f"地点检索完成：{query.keyword}",
                payload={"result_count": len(output.results)},
            )
            for place in output.results:
                candidates.setdefault(
                    place.provider_place_id,
                    place.model_dump(mode="json"),
                )
    except ToolLimitExceeded:
        return _failed(
            graph_runtime,
            error_code="tool_limit_exceeded",
            message="工具调用达到上限",
            tool_call_count=graph_runtime.tools.call_count,
        )
    except ToolDeadlineExceeded:
        return _failed(
            graph_runtime,
            error_code="graph_timeout",
            message="工具调用超过任务时限",
            tool_call_count=graph_runtime.tools.call_count,
        )
    except ToolTimeoutError:
        return _failed(
            graph_runtime,
            error_code="graph_timeout",
            message="工具调用超时",
            tool_call_count=graph_runtime.tools.call_count,
        )
    except LlmTimeoutError:
        return _failed(
            graph_runtime,
            error_code="graph_timeout",
            message="模型工具选择超时",
            tool_call_count=graph_runtime.tools.call_count,
        )
    except LlmRateLimitError:
        return _failed(
            graph_runtime,
            error_code="llm_rate_limited",
            message="模型工具选择触发限流",
            tool_call_count=graph_runtime.tools.call_count,
        )
    except LlmProviderError:
        return _failed(
            graph_runtime,
            error_code="llm_provider_error",
            message="模型工具选择失败",
            tool_call_count=graph_runtime.tools.call_count,
        )
    if not candidates:
        return _failed(
            graph_runtime,
            error_code="provider_error" if failed_queries else "no_candidates",
            message=(
                "地点 Provider 调用失败"
                if failed_queries
                else "没有找到可用的候选地点"
            ),
            tool_call_count=graph_runtime.tools.call_count,
        )
    graph_runtime.emit(
        "stage",
        stage="research_complete",
        message="候选地点已准备完成",
        payload={
            "candidate_count": len(candidates),
            "failed_query_count": failed_queries,
        },
    )
    return {
        "status": "running",
        "candidates": list(candidates.values()),
        "tool_call_count": graph_runtime.tools.call_count,
        "input_tokens": int(state.get("input_tokens", 0)) + plan.input_tokens,
        "output_tokens": int(state.get("output_tokens", 0)) + plan.output_tokens,
        "latency_ms": int(state.get("latency_ms", 0)) + plan.latency_ms,
        "estimated_cost_minor": int(
            state.get("estimated_cost_minor", 0)
        )
        + plan.estimated_cost_minor,
        "model_name": plan.model_name or state.get("model_name", ""),
        "provider_name": plan.provider_name
        or research_planner.provider_name,
        "prompt_versions": [
            *[
                dict(item)
                for item in state.get("prompt_versions", [])
            ],
            *plan.prompt_versions,
        ],
        "events": graph_runtime.event_dicts(),
    }


def _failed(
    graph_runtime: GraphRuntime,
    *,
    error_code: str,
    message: str,
    tool_call_count: int,
) -> dict[str, object]:
    graph_runtime.emit("error", status="failed", message=message)
    return {
        "status": "failed",
        "error_code": error_code,
        "error_message": message,
        "tool_call_count": tool_call_count,
        "events": graph_runtime.event_dicts(),
    }
