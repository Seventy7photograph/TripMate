# 文件说明：Pydantic 数据契约：patch。
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.itinerary import ItineraryResponse


class ReplanRequest(BaseModel):
    expected_version: int = Field(ge=1)
    day_id: UUID
    instruction: str = Field(min_length=1, max_length=2_000)

    @field_validator("instruction")
    @classmethod
    def normalize_instruction(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("instruction cannot be blank")
        return normalized


class PatchChangeResponse(BaseModel):
    target_day_date: date
    removed_stop_ids: list[UUID]
    added_stop_ids: list[UUID]
    before_stops: list[dict[str, object]]
    after_stops: list[dict[str, object]]
    before_stop_count: int
    after_stop_count: int


class PatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID
    target_day_id: UUID
    base_version: int
    applied_version: int | None
    status: Literal["pending", "applied", "discarded"]
    instruction: str
    changes: PatchChangeResponse
    created_at: datetime
    applied_at: datetime | None


class PatchActionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class PatchApplyResponse(PatchResponse):
    itinerary: ItineraryResponse
