# 文件说明：后端自动化测试：test_budget_properties。
from datetime import date
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.budget import Expense, build_budget_summary

CATEGORIES = ["transport", "lodging", "food", "tickets", "shopping", "activities", "other"]


@settings(max_examples=80, deadline=None)
@given(
    amounts=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        max_size=30,
    ),
    stop_costs=st.lists(
        st.integers(min_value=0, max_value=1_000_000),
        max_size=20,
    ),
    party_size=st.integers(min_value=1, max_value=20),
)
def test_category_totals_always_equal_actual_total(
    amounts: list[int],
    stop_costs: list[int],
    party_size: int,
) -> None:
    trip_id = uuid4()
    expenses = [
        Expense(
            id=uuid4(),
            trip_id=trip_id,
            payer_id=uuid4(),
            category=CATEGORIES[index % len(CATEGORIES)],
            amount_minor=amount,
            currency="CNY",
            expense_date=date(2026, 12, 1),
            note=None,
            created_at=None,
        )
        for index, amount in enumerate(amounts)
    ]

    summary = build_budget_summary(
        trip_id=trip_id,
        version=1,
        currency="CNY",
        budget_minor=None,
        party_size=party_size,
        stop_costs_minor=stop_costs,
        expenses=expenses,
    )

    assert summary.total_minor == sum(amounts)
    assert sum(category.actual_minor for category in summary.categories) == sum(amounts)
    assert summary.estimated_minor == sum(stop_costs)
    assert sum(category.estimated_minor for category in summary.categories) == sum(
        stop_costs
    )
