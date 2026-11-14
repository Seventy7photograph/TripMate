# 文件说明：Pydantic 数据契约：budget。
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.budget import ExpenseCategory


class ExpenseCreateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    category: ExpenseCategory
    amount_minor: int = Field(ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    expense_date: date = Field(default_factory=date.today)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter code")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID
    payer_id: UUID
    category: ExpenseCategory
    amount_minor: int
    currency: str
    expense_date: date
    note: str | None
    created_at: datetime


class ExpenseCreateResponse(BaseModel):
    version: int
    expense: ExpenseResponse


class BudgetCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: ExpenseCategory
    estimated_minor: int
    actual_minor: int


class BudgetIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: Literal["info", "warning", "error", "fatal"]
    message: str
    overage_minor: int


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: UUID
    version: int
    currency: str
    budget_minor: int | None
    estimated_minor: int
    total_minor: int
    per_person_minor: int
    remaining_minor: int | None
    estimated_remaining_minor: int | None
    categories: list[BudgetCategoryResponse]
    issues: list[BudgetIssueResponse]
    expenses: list[ExpenseResponse]
