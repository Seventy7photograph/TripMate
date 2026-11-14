# 文件说明：数据访问仓储：expense_repository。
from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.budget import Expense, ExpenseCategory
from app.models.expense import Expense as ExpenseModel


class ExpenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        trip_id: UUID,
        payer_id: UUID,
        category: ExpenseCategory,
        amount_minor: int,
        currency: str,
        expense_date: date,
        note: str | None,
    ) -> Expense:
        model = ExpenseModel(
            trip_id=trip_id,
            payer_id=payer_id,
            category=category,
            amount_minor=amount_minor,
            currency=currency,
            expense_date=expense_date,
            note=note,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def list_for_trip(self, trip_id: UUID) -> list[Expense]:
        result = await self._session.execute(
            select(ExpenseModel)
            .where(ExpenseModel.trip_id == trip_id)
            .order_by(ExpenseModel.expense_date, ExpenseModel.created_at)
        )
        return [self._to_domain(model) for model in result.scalars()]

    @staticmethod
    def _to_domain(model: ExpenseModel) -> Expense:
        return Expense(
            id=model.id,
            trip_id=model.trip_id,
            payer_id=model.payer_id,
            category=cast(ExpenseCategory, model.category),
            amount_minor=model.amount_minor,
            currency=model.currency,
            expense_date=model.expense_date,
            note=model.note,
            created_at=model.created_at,
        )
