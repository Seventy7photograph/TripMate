# 文件说明：Pydantic 数据契约：memory。
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MemoryCategory = Literal[
    "preference",
    "food",
    "mobility",
    "lodging",
    "budget",
    "avoid",
    "other",
]


class MemoryCreateRequest(BaseModel):
    category: MemoryCategory = "preference"
    content: str = Field(min_length=1, max_length=1_000)
    consent: bool = False

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content cannot be blank")
        return normalized


class MemoryUpdateRequest(BaseModel):
    category: MemoryCategory | None = None
    content: str | None = Field(default=None, min_length=1, max_length=1_000)
    enabled: bool | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("content cannot be blank")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.category is None and self.content is None and self.enabled is None:
            raise ValueError("at least one memory field is required")
        return self


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: MemoryCategory
    content: str
    enabled: bool
    source: str
    consent_at: datetime
    created_at: datetime
    updated_at: datetime
