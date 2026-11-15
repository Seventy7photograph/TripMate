# 文件说明：LangGraph 节点：build_itinerary。
import inspect

from app.agents.itinerary_composer import (
    ItineraryComposer,
    RetryableCompositionError,
)
from app.graph.runtime import GraphRuntime
from app.graph.state import TravelGraphState
from app.providers.llm.base import (
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.schemas.ai import TripBriefContract


async def build_itinerary_node(
    state: TravelGraphState,
    *,
    graph_runtime: GraphRuntime,
    composer: ItineraryComposer,
    max_loops: int,
    max_cost_minor: int,
) -> dict[str, object]:
    attempt = int(state.get("composer_attempts", 0)) + 1
    loop_count = int(state.get("loop_count", 0))
    graph_runtime.emit(
        "stage",
        stage="compose",
        message="正在组合候选地点与每日时间",
        payload={"attempt": attempt},
    )
    try:
        brief = TripBriefContract.model_validate(state["brief"])
        compose_kwargs: dict[str, object] = {
            "trip_id": str(state["trip_id"]),
            "version": int(state["version"]),
            "brief": brief,
            "candidates": state["candidates"],
        }
        parameters = inspect.signature(composer.compose).parameters
        if "evidence_ids" in parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            compose_kwargs["evidence_ids"] = state.get(
                "evidence_ids_by_place",
                {},
            )
        if "skill_results" in parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            compose_kwargs["skill_results"] = state.get(
                "skill_results",
                {},
            )
        result = await composer.compose(**compose_kwargs)  # type: ignore[arg-type]
    except RetryableCompositionError as exc:
        if loop_count >= max_loops:
            graph_runtime.emit("error", status="failed", message="行程生成达到修复上限")
            return {
                "status": "failed",
                "error_code": "max_loops_exceeded",
                "error_message": f"Maximum replan loops reached: {exc.code}",
                "loop_count": loop_count,
                "composer_attempts": attempt,
                "events": graph_runtime.event_dicts(),
            }
        graph_runtime.emit(
            "stage",
            stage="repair",
            message="行程组合未通过，执行有限重试",
            payload={"issue_code": exc.code, "loop": loop_count + 1},
        )
        return {
            "status": "retrying",
            "loop_count": loop_count + 1,
            "composer_attempts": attempt,
            "error_code": None,
            "error_message": None,
            "events": graph_runtime.event_dicts(),
        }
    except LlmTimeoutError:
        graph_runtime.emit("error", status="failed", message="行程模型调用超时")
        return {
            "status": "failed",
            "error_code": "graph_timeout",
            "error_message": "Itinerary model call timed out",
            "composer_attempts": attempt,
            "events": graph_runtime.event_dicts(),
        }
    except LlmRateLimitError:
        graph_runtime.emit("error", status="failed", message="行程模型调用触发限流")
        return {
            "status": "failed",
            "error_code": "llm_rate_limited",
            "error_message": "Itinerary model call rate limited",
            "composer_attempts": attempt,
            "events": graph_runtime.event_dicts(),
        }
    except LlmProviderError as exc:
        detail = str(exc).strip()[:500] or "LLM provider failed"
        graph_runtime.emit(
            "error",
            status="failed",
            message=f"行程模型服务失败：{detail}",
        )
        return {
            "status": "failed",
            "error_code": "llm_provider_error",
            "error_message": detail,
            "composer_attempts": attempt,
            "events": graph_runtime.event_dicts(),
        }
    except Exception:
        graph_runtime.emit("error", status="failed", message="行程组合失败")
        return {
            "status": "failed",
            "error_code": "composition_failed",
            "error_message": "Itinerary composition failed",
            "composer_attempts": attempt,
            "events": graph_runtime.event_dicts(),
        }

    if result.estimated_cost_minor > max_cost_minor:
        graph_runtime.emit("error", status="failed", message="模型成本超过单次任务上限")
        return {
            "status": "failed",
            "error_code": "cost_limit_exceeded",
            "error_message": "Estimated model cost exceeded the run limit",
            "composer_attempts": attempt,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
            "estimated_cost_minor": result.estimated_cost_minor,
            "model_name": result.model_name,
            "provider_name": result.provider_name,
            "prompt_versions": [
                *[
                    dict(item)
                    for item in state.get("prompt_versions", [])
                ],
                *result.prompt_versions,
            ],
            "events": graph_runtime.event_dicts(),
        }

    graph_runtime.emit(
        "stage",
        stage="draft_ready",
        message="初始行程草案已生成，进入规则校验",
    )
    return {
        "status": "completed",
        "draft": result.draft.model_dump(mode="json"),
        "issues": [],
        "tool_call_count": graph_runtime.tools.call_count,
        "composer_attempts": attempt,
        "input_tokens": int(state.get("input_tokens", 0)) + result.input_tokens,
        "output_tokens": int(state.get("output_tokens", 0)) + result.output_tokens,
        "latency_ms": int(state.get("latency_ms", 0)) + result.latency_ms,
        "estimated_cost_minor": result.estimated_cost_minor,
        "model_name": result.model_name,
        "provider_name": result.provider_name,
        "prompt_versions": [
            *[
                dict(item)
                for item in state.get("prompt_versions", [])
            ],
            *result.prompt_versions,
        ],
        "events": graph_runtime.event_dicts(),
    }
