# 文件说明：领域对象：budget。
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

ExpenseCategory = Literal[
    "transport",
    "lodging",
    "food",
    "tickets",
    "shopping",
    "activities",
    "other",
]

EXPENSE_CATEGORIES: tuple[ExpenseCategory, ...] = (
    "transport",
    "lodging",
    "food",
    "tickets",
    "shopping",
    "activities",
    "other",
)


@dataclass(frozen=True, slots=True)
class Expense:
    id: UUID
    trip_id: UUID
    payer_id: UUID
    category: ExpenseCategory
    amount_minor: int
    currency: str
    expense_date: date
    note: str | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class BudgetCategoryTotal:
    category: ExpenseCategory
    estimated_minor: int
    actual_minor: int


@dataclass(frozen=True, slots=True)
class BudgetIssue:
    code: str
    severity: Literal["info", "warning", "error", "fatal"]
    message: str
    overage_minor: int


@dataclass(frozen=True, slots=True)
class BudgetSummary:
    trip_id: UUID
    version: int
    currency: str
    budget_minor: int | None
    estimated_minor: int
    total_minor: int
    per_person_minor: int
    remaining_minor: int | None
    estimated_remaining_minor: int | None
    categories: list[BudgetCategoryTotal]
    issues: list[BudgetIssue]
    expenses: list[Expense]


def build_budget_summary(
    *,
    trip_id: UUID,
    version: int,
    currency: str,
    budget_minor: int | None,
    party_size: int,
    stop_costs_minor: list[int],
    expenses: list[Expense],
) -> BudgetSummary:
    estimated_by_category = {category: 0 for category in EXPENSE_CATEGORIES}
    actual_by_category = {category: 0 for category in EXPENSE_CATEGORIES}
    estimated_by_category["activities"] = sum(stop_costs_minor)
    for expense in expenses:
        actual_by_category[expense.category] += expense.amount_minor

    estimated_total = sum(estimated_by_category.values())
    actual_total = sum(actual_by_category.values())
    per_person = int(
        (Decimal(actual_total) / Decimal(party_size)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    remaining = budget_minor - actual_total if budget_minor is not None else None
    estimated_remaining = (
        budget_minor - estimated_total if budget_minor is not None else None
    )

    issues: list[BudgetIssue] = []
    if budget_minor is not None and actual_total > budget_minor:
        issues.append(
            BudgetIssue(
                code="budget_exceeded",
                severity="warning",
                message="实际支出超过旅行预算",
                overage_minor=actual_total - budget_minor,
            )
        )
    elif budget_minor is not None and estimated_total > budget_minor:
        issues.append(
            BudgetIssue(
                code="budget_exceeded",
                severity="warning",
                message="预计支出超过旅行预算",
                overage_minor=estimated_total - budget_minor,
            )
        )

    return BudgetSummary(
        trip_id=trip_id,
        version=version,
        currency=currency,
        budget_minor=budget_minor,
        estimated_minor=estimated_total,
        total_minor=actual_total,
        per_person_minor=per_person,
        remaining_minor=remaining,
        estimated_remaining_minor=estimated_remaining,
        categories=[
            BudgetCategoryTotal(
                category=category,
                estimated_minor=estimated_by_category[category],
                actual_minor=actual_by_category[category],
            )
            for category in EXPENSE_CATEGORIES
        ],
        issues=issues,
        expenses=expenses,
    )
