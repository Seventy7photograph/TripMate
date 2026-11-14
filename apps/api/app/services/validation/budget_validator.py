# 文件说明：确定性校验器：budget_validator。
from typing import Protocol

from app.schemas.ai import (
    ItineraryDraftContract,
    TripBriefContract,
    ValidationIssueContract,
)
from app.tools.budget_tools import BudgetToolInput, BudgetToolResult


class BudgetLookup(Protocol):
    async def calculate(self, request: BudgetToolInput) -> BudgetToolResult: ...


async def validate_budget(
    draft: ItineraryDraftContract,
    *,
    brief: TripBriefContract,
    budget_lookup: BudgetLookup,
) -> list[ValidationIssueContract]:
    result = await budget_lookup.calculate(
        BudgetToolInput(
            stop_costs_minor=[
                stop.estimated_cost_minor
                for day in draft.days
                for stop in day.stops
            ],
            budget_minor=brief.budget_minor,
        )
    )
    if result.within_budget:
        return []
    overage = abs(result.remaining_minor or 0)
    return [
        ValidationIssueContract(
            code="budget_exceeded",
            severity="warning",
            path="budget",
            message=f"预计费用超出预算 {overage} 分",
            repair_hint="移除优先级较低的非锁定地点",
        )
    ]
