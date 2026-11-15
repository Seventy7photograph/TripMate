# 文件说明：AI Agent：research_planner。
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings
from app.prompts.catalog import prompt_request_metadata
from app.prompts.registry import RESEARCH_PLANNER_TOOL_SELECTION, load_prompt
from app.providers.base import PlaceQuery
from app.providers.llm.base import (
    ToolCallingLlmProvider,
    ToolCallingRequest,
    ToolDefinition,
)
from app.providers.llm.factory import build_llm_provider
from app.schemas.ai import TripBriefContract
from app.tools.place_tools import PlaceTool


@dataclass(frozen=True, slots=True)
class ResearchPlanResult:
    queries: list[PlaceQuery]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost_minor: int = 0
    model_name: str = ""
    provider_name: str = ""
    prompt_versions: list[dict[str, str]] = field(default_factory=list)


class ResearchPlanner(Protocol):
    provider_name: str
    model_name: str

    async def plan(
        self,
        *,
        brief: TripBriefContract,
        tools: list[ToolDefinition],
    ) -> ResearchPlanResult: ...


class MockResearchPlanner:
    provider_name = "mock"
    model_name = "mock-research-planner"

    async def plan(
        self,
        *,
        brief: TripBriefContract,
        tools: list[ToolDefinition],
    ) -> ResearchPlanResult:
        del tools
        queries: list[PlaceQuery] = []
        seen: set[str] = set()
        for item in brief.must_visit[:3]:
            keyword = item.strip()
            if keyword and keyword not in seen:
                queries.append(
                    PlaceQuery(keyword=keyword, city=brief.destination, limit=5)
                )
                seen.add(keyword)
        destination_query = f"{brief.destination} 景点"
        if destination_query not in seen:
            queries.append(
                PlaceQuery(
                    keyword=destination_query,
                    city=brief.destination,
                    limit=5,
                )
            )
        return ResearchPlanResult(
            queries=queries,
            provider_name=self.provider_name,
            model_name=self.model_name,
        )


class LlmResearchPlanner:
    def __init__(self, provider: ToolCallingLlmProvider) -> None:
        self._provider = provider
        self.provider_name = provider.provider_name
        self.model_name = provider.model_name
        self._prompt = load_prompt(RESEARCH_PLANNER_TOOL_SELECTION)

    async def plan(
        self,
        *,
        brief: TripBriefContract,
        tools: list[ToolDefinition],
    ) -> ResearchPlanResult:
        tool_definitions = tools or [
            ToolDefinition(
                name=str(PlaceTool.schema()["name"]),
                description=str(PlaceTool.schema()["description"]),
                parameters=PlaceTool.schema()["parameters"],  # type: ignore[arg-type]
            )
        ]
        response = await self._provider.generate_with_tools(
            ToolCallingRequest(
                system_prompt=self._prompt.content,
                user_prompt=(
                    "TripBrief:\n"
                    f"{brief.model_dump_json()}\n"
                    "请选择地点检索调用。"
                ),
                user_text=brief.model_dump_json(),
                tools=tool_definitions,
                metadata=prompt_request_metadata(
                    self._prompt,
                    operation="research_tool_selection",
                ),
            )
        )
        queries: list[PlaceQuery] = []
        seen: set[str] = set()
        for call in response.tool_calls:
            if call.name != "search_places":
                continue
            keyword = str(call.arguments.get("keyword") or "").strip()
            if not keyword or keyword in seen:
                continue
            city = call.arguments.get("city")
            raw_limit = call.arguments.get("limit", 5)
            limit = (
                max(1, min(20, int(raw_limit)))
                if isinstance(raw_limit, int)
                else 5
            )
            queries.append(
                PlaceQuery(
                    keyword=keyword,
                    city=str(city) if city is not None else brief.destination,
                    limit=limit,
                )
            )
            seen.add(keyword)
            if len(queries) >= 3:
                break
        return ResearchPlanResult(
            queries=queries,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=response.usage.latency_ms,
            estimated_cost_minor=response.usage.estimated_cost_minor,
            model_name=response.usage.model_name or self.model_name,
            provider_name=self.provider_name,
            prompt_versions=[self._prompt.audit_record()],
        )


def create_research_planner(settings: Settings) -> ResearchPlanner:
    if settings.provider_profile == "mock":
        return MockResearchPlanner()
    provider = build_llm_provider(settings)
    if not hasattr(provider, "generate_with_tools"):
        raise RuntimeError("live LLM provider does not support function calling")
    return LlmResearchPlanner(provider)  # type: ignore[arg-type]
