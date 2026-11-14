# 文件说明：后端自动化测试：test_budget。
from datetime import date
from uuid import uuid4

import httpx

from app.domain.budget import Expense, build_budget_summary
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def create_trip(
    api_client: httpx.AsyncClient,
    token: str,
    *,
    budget_minor: int | None = 100_000,
    currency: str = "CNY",
) -> dict[str, object]:
    payload = trip_payload(
        destination="Chongqing",
        budget_minor=budget_minor,
        currency=currency,
        party_size=2,
    )
    response = await api_client.post(
        "/api/v1/trips",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_stop_cost(
    api_client: httpx.AsyncClient,
    token: str,
    trip_id: str,
    *,
    cost_minor: int,
    expected_version: int,
) -> None:
    day_response = await api_client.post(
        f"/api/v1/trips/{trip_id}/days",
        headers=auth_headers(token),
        json={"date": "2026-12-01", "expected_version": expected_version},
    )
    assert day_response.status_code == 201, day_response.text
    day_id = day_response.json()["id"]
    stop_response = await api_client.post(
        f"/api/v1/days/{day_id}/stops",
        headers=auth_headers(token),
        json={
            "place_id": f"manual-budget-{uuid4().hex}",
            "place_name": "Budget stop",
            "start_at": "2026-12-01T09:00:00",
            "duration_minutes": 60,
            "estimated_cost_minor": cost_minor,
            "expected_version": expected_version + 1,
        },
    )
    assert stop_response.status_code == 201, stop_response.text


async def test_budget_combines_itinerary_estimates_and_actual_expenses(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)
    await add_stop_cost(
        api_client,
        token,
        str(trip["id"]),
        cost_minor=50_000,
        expected_version=1,
    )

    transport = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 3,
            "category": "transport",
            "amount_minor": 25_000,
            "expense_date": "2026-12-01",
        },
    )
    assert transport.status_code == 201, transport.text
    assert transport.json()["expense"]["currency"] == "CNY"
    assert transport.json()["version"] == 4

    food = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 4,
            "category": "food",
            "amount_minor": 10_000,
            "currency": "CNY",
            "expense_date": "2026-12-01",
        },
    )
    assert food.status_code == 201, food.text
    assert food.json()["version"] == 5

    budget = await api_client.get(
        f"/api/v1/trips/{trip['id']}/budget",
        headers=auth_headers(token),
    )
    assert budget.status_code == 200, budget.text
    payload = budget.json()
    assert payload["currency"] == "CNY"
    assert payload["budget_minor"] == 100_000
    assert payload["estimated_minor"] == 50_000
    assert payload["total_minor"] == 35_000
    assert payload["per_person_minor"] == 17_500
    assert payload["remaining_minor"] == 65_000
    assert payload["estimated_remaining_minor"] == 50_000
    assert payload["version"] == 5
    assert sum(item["actual_minor"] for item in payload["categories"]) == 35_000
    assert sum(item["estimated_minor"] for item in payload["categories"]) == 50_000
    assert payload["issues"] == []


async def test_budget_exceeded_returns_structured_issue(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token, budget_minor=10_000)

    response = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "category": "tickets",
            "amount_minor": 12_000,
            "currency": "CNY",
            "expense_date": "2026-12-01",
        },
    )
    assert response.status_code == 201, response.text

    budget = await api_client.get(
        f"/api/v1/trips/{trip['id']}/budget",
        headers=auth_headers(token),
    )
    payload = budget.json()
    assert payload["remaining_minor"] == -2_000
    assert payload["issues"] == [
        {
            "code": "budget_exceeded",
            "severity": "warning",
            "message": "实际支出超过旅行预算",
            "overage_minor": 2_000,
        }
    ]


async def test_expense_currency_and_amount_are_validated(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)

    wrong_currency = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "category": "food",
            "amount_minor": 100,
            "currency": "USD",
            "expense_date": "2026-12-01",
        },
    )
    assert wrong_currency.status_code == 422

    negative = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "category": "food",
            "amount_minor": -1,
            "currency": "CNY",
            "expense_date": "2026-12-01",
        },
    )
    assert negative.status_code == 422

    zero = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "category": "other",
            "amount_minor": 0,
            "currency": "CNY",
            "expense_date": "2026-12-01",
        },
    )
    assert zero.status_code == 201


async def test_expense_access_is_isolated_by_trip_owner(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"budget-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"budget-outsider-{uuid4().hex}@example.com",
    )
    owner_token = str(owner["access_token"])
    outsider_token = str(outsider["access_token"])
    trip = await create_trip(api_client, owner_token)

    read = await api_client.get(
        f"/api/v1/trips/{trip['id']}/budget",
        headers=auth_headers(outsider_token),
    )
    assert read.status_code == 404

    create = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(outsider_token),
        json={
            "expected_version": 1,
            "category": "food",
            "amount_minor": 100,
        },
    )
    assert create.status_code == 404


async def test_expenses_follow_trip_version_snapshot_restore(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = await create_trip(api_client, token)

    first = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "category": "food",
            "amount_minor": 1_100,
            "expense_date": "2026-12-01",
        },
    )
    assert first.status_code == 201
    second = await api_client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=auth_headers(token),
        json={
            "expected_version": 2,
            "category": "tickets",
            "amount_minor": 2_200,
            "expense_date": "2026-12-01",
        },
    )
    assert second.status_code == 201

    restored_empty = await api_client.post(
        f"/api/v1/trips/{trip['id']}/versions/1/restore",
        headers=auth_headers(token),
        json={"expected_version": 3},
    )
    assert restored_empty.status_code == 200
    empty_budget = await api_client.get(
        f"/api/v1/trips/{trip['id']}/budget",
        headers=auth_headers(token),
    )
    assert empty_budget.json()["total_minor"] == 0
    assert empty_budget.json()["expenses"] == []

    restored_first = await api_client.post(
        f"/api/v1/trips/{trip['id']}/versions/2/restore",
        headers=auth_headers(token),
        json={"expected_version": 4},
    )
    assert restored_first.status_code == 200
    restored_budget = await api_client.get(
        f"/api/v1/trips/{trip['id']}/budget",
        headers=auth_headers(token),
    )
    assert restored_budget.json()["total_minor"] == 1_100
    assert len(restored_budget.json()["expenses"]) == 1


def test_budget_calculator_uses_decimal_rounding_and_integer_minor_units() -> None:
    expenses = [
        Expense(
            id=uuid4(),
            trip_id=uuid4(),
            payer_id=uuid4(),
            category="food",
            amount_minor=1,
            currency="CNY",
            expense_date=date(2026, 12, 1),
            note=None,
            created_at=None,
        )
    ]
    summary = build_budget_summary(
        trip_id=uuid4(),
        version=1,
        currency="CNY",
        budget_minor=100,
        party_size=3,
        stop_costs_minor=[2],
        expenses=expenses,
    )
    assert summary.total_minor == 1
    assert summary.per_person_minor == 0
    assert summary.estimated_minor == 2
