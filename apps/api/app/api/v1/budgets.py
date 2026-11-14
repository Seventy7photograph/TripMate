# 文件说明：FastAPI 路由：budgets。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.budget import (
    BudgetResponse,
    ExpenseCreateRequest,
    ExpenseCreateResponse,
    ExpenseResponse,
)
from app.services.budget_service import (
    BudgetService,
    BudgetTripNotFoundError,
    ExpenseCurrencyMismatchError,
)
from app.services.version_service import VersionConflictError

router = APIRouter(tags=["budget"])


def get_budget_service(session: SessionDep) -> BudgetService:
    return BudgetService(session)


BudgetServiceDep = Annotated[BudgetService, Depends(get_budget_service)]


def not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Trip not found",
    )


def version_conflict(exc: VersionConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "version_conflict",
            "message": "Trip was updated by another session",
            "current_version": exc.current_version,
        },
    )


@router.get("/trips/{trip_id}/budget", response_model=BudgetResponse)
async def get_budget(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: BudgetServiceDep,
) -> BudgetResponse:
    try:
        budget = await service.get(owner_id=current_user.id, trip_id=trip_id)
    except BudgetTripNotFoundError as exc:
        raise not_found() from exc
    return BudgetResponse.model_validate(budget)


@router.post(
    "/trips/{trip_id}/expenses",
    response_model=ExpenseCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    trip_id: UUID,
    payload: ExpenseCreateRequest,
    current_user: CurrentUserDep,
    service: BudgetServiceDep,
) -> ExpenseCreateResponse:
    try:
        result = await service.create_expense(
            owner_id=current_user.id,
            trip_id=trip_id,
            expected_version=payload.expected_version,
            category=payload.category,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            expense_date=payload.expense_date,
            note=payload.note,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except BudgetTripNotFoundError as exc:
        raise not_found() from exc
    except ExpenseCurrencyMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Expense currency must match the trip currency",
        ) from exc
    return ExpenseCreateResponse(
        version=result.version,
        expense=ExpenseResponse.model_validate(result.expense),
    )
