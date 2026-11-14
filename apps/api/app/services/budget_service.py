# 文件说明：业务服务：budget_service。
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.budget import (
    BudgetSummary,
    Expense,
    ExpenseCategory,
    build_budget_summary,
)
from app.models.trip import Trip as TripModel
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.trip_repository import TripRepository
from app.services.version_service import VersionService, VersionTripNotFoundError


class BudgetTripNotFoundError(Exception):
    pass


class ExpenseCurrencyMismatchError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ExpenseCreateResult:
    expense: Expense
    version: int


class BudgetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._trips = TripRepository(session)
        self._itinerary = ItineraryRepository(session)
        self._expenses = ExpenseRepository(session)
        self._versions = VersionService(session)

    async def get(self, *, owner_id: UUID, trip_id: UUID) -> BudgetSummary:
        trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise BudgetTripNotFoundError
        days = await self._itinerary.list_days(trip_id=trip.id)
        expenses = await self._expenses.list_for_trip(trip.id)
        return build_budget_summary(
            trip_id=trip.id,
            version=trip.version,
            currency=trip.brief.currency,
            budget_minor=trip.brief.budget_minor,
            party_size=trip.brief.party_size,
            stop_costs_minor=[
                stop.estimated_cost_minor
                for day in days
                for stop in day.stops
            ],
            expenses=expenses,
        )

    async def create_expense(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
        category: ExpenseCategory,
        amount_minor: int,
        currency: str,
        expense_date: date,
        note: str | None,
    ) -> ExpenseCreateResult:
        locked_trip = await self._lock_trip(
            owner_id=owner_id,
            trip_id=trip_id,
            expected_version=expected_version,
        )
        trip_currency = str(locked_trip.brief["currency"])
        if currency.upper() != trip_currency.upper():
            raise ExpenseCurrencyMismatchError

        expense = await self._expenses.create(
            trip_id=locked_trip.id,
            payer_id=owner_id,
            category=category,
            amount_minor=amount_minor,
            currency=currency.upper(),
            expense_date=expense_date,
            note=note,
        )
        await self._versions.complete_write(model=locked_trip, created_by=owner_id)
        await self._session.commit()
        return ExpenseCreateResult(expense=expense, version=locked_trip.version)

    async def _lock_trip(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
    ) -> TripModel:
        try:
            return await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise BudgetTripNotFoundError from exc
