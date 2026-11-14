# 文件说明：Agent 受控工具：budget_tools。
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec


class BudgetToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_costs_minor: list[Annotated[int, Field(ge=0)]]
    budget_minor: int | None = Field(default=None, ge=0)


class BudgetToolResult(BaseModel):
    estimated_minor: int
    remaining_minor: int | None
    within_budget: bool


_CALCULATE_BUDGET_SPEC = ToolSpec(
    name="calculate_budget",
    description="Calculate estimated itinerary cost using integer minor units.",
    input_model=BudgetToolInput,
    output_model=BudgetToolResult,
    provider_type="deterministic",
    risk="read",
    timeout_seconds=2.0,
    max_retries=0,
)


class BudgetTool:
    name = _CALCULATE_BUDGET_SPEC.name
    provider = "deterministic"

    def __init__(self, context: ToolContext) -> None:
        self._context = context
        self._cache: dict[tuple[tuple[int, ...], int | None], BudgetToolResult] = {}

    async def calculate(self, request: BudgetToolInput) -> BudgetToolResult:
        cache_key = (tuple(request.stop_costs_minor), request.budget_minor)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        result = await self.invoke(self._context, request)
        output = BudgetToolResult.model_validate(result)
        self._cache[cache_key] = output
        return output

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = BudgetToolInput.model_validate(payload)
        return await context.runner.call(
            tool_name=self.name,
            provider=self.provider,
            input_payload=request.model_dump(),
            operation=lambda: self._calculate(request),
            timeout_seconds=_CALCULATE_BUDGET_SPEC.timeout_seconds,
            max_retries=_CALCULATE_BUDGET_SPEC.max_retries,
        )

    @staticmethod
    async def _calculate(request: BudgetToolInput) -> BudgetToolResult:
        estimated = sum(request.stop_costs_minor)
        remaining = (
            request.budget_minor - estimated
            if request.budget_minor is not None
            else None
        )
        return BudgetToolResult(
            estimated_minor=estimated,
            remaining_minor=remaining,
            within_budget=remaining is None or remaining >= 0,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _CALCULATE_BUDGET_SPEC

    @staticmethod
    def schema() -> dict[str, object]:
        parameters = dict(BudgetToolInput.model_json_schema())
        parameters["additionalProperties"] = False
        return {
            "name": _CALCULATE_BUDGET_SPEC.name,
            "description": _CALCULATE_BUDGET_SPEC.description,
            "parameters": parameters,
        }
