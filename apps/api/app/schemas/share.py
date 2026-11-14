# 文件说明：Pydantic 数据契约：share。
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FavoriteKind = Literal["place", "trip"]


class FavoriteCreateRequest(BaseModel):
    kind: FavoriteKind
    target_id: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    folder: str | None = Field(default=None, min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=2_000)
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("target_id", "label", "folder")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class FavoriteUpdateRequest(BaseModel):
    folder: str | None = Field(default=None, min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=2_000)

    @field_validator("folder")
    @classmethod
    def normalize_folder(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("folder cannot be blank")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class FavoriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: FavoriteKind
    target_id: str
    label: str
    folder: str
    note: str | None
    details: dict[str, object]
    created_at: datetime


class ShareCreateRequest(BaseModel):
    expires_in_days: int = Field(default=30, ge=1, le=365)


class ShareCreateResponse(BaseModel):
    id: UUID
    token: str
    url_path: str
    expires_at: datetime
    created_at: datetime


class ShareSummaryResponse(BaseModel):
    id: UUID
    trip_id: UUID
    status: Literal["active", "expired", "revoked"]
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class PublicStopResponse(BaseModel):
    place_id: str
    place_name: str | None
    start_at: datetime
    duration_minutes: int
    location: dict[str, object] | None


class PublicDayResponse(BaseModel):
    date: date
    day_index: int
    theme: str | None
    stops: list[PublicStopResponse]


class PublicTripResponse(BaseModel):
    version: int
    destination: str
    origin: str | None
    start_date: date
    end_date: date
    party_size: int
    currency: str
    days: list[PublicDayResponse]
    generated_at: datetime


class TripExportResponse(PublicTripResponse):
    filename: str
