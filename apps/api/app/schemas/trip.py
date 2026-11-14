# 文件说明：Pydantic 数据契约：trip。
from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.trip import TripBrief, TripPace, TripStatus


class TripBriefPayload(BaseModel):
    destination: str = Field(min_length=1, max_length=120)
    origin: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date
    party_size: int = Field(ge=1, le=20)
    budget_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    interests: list[str] = Field(default_factory=list, max_length=20)
    pace: TripPace = "balanced"
    transport_preferences: list[str] = Field(default_factory=list, max_length=20)
    lodging_preferences: list[str] = Field(default_factory=list, max_length=20)
    must_visit: list[str] = Field(default_factory=list, max_length=20)
    avoid: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("destination", "origin")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("text fields cannot be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter code")
        return normalized

    @field_validator(
        "interests",
        "transport_preferences",
        "lodging_preferences",
        "must_visit",
        "avoid",
        "constraints",
    )
    @classmethod
    def normalize_list(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in normalized:
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self

    def to_domain(self) -> TripBrief:
        return TripBrief(
            destination=self.destination,
            origin=self.origin,
            start_date=self.start_date,
            end_date=self.end_date,
            party_size=self.party_size,
            budget_minor=self.budget_minor,
            currency=self.currency,
            interests=self.interests,
            pace=self.pace,
            transport_preferences=self.transport_preferences,
            lodging_preferences=self.lodging_preferences,
            must_visit=self.must_visit,
            avoid=self.avoid,
            constraints=self.constraints,
        )


class TripCreateRequest(BaseModel):
    brief: TripBriefPayload


class TripUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    brief: TripBriefPayload | None = None
    status: TripStatus | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.brief is None and self.status is None:
            raise ValueError("at least one trip field is required")
        return self


class TripBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    destination: str
    origin: str | None
    start_date: date
    end_date: date
    party_size: int
    budget_minor: int | None
    currency: str
    interests: list[str]
    pace: TripPace
    transport_preferences: list[str]
    lodging_preferences: list[str]
    must_visit: list[str]
    avoid: list[str]
    constraints: list[str]


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    status: TripStatus
    version: int
    brief: TripBriefResponse
    created_at: datetime
    updated_at: datetime
