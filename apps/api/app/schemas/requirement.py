# 文件说明：Pydantic 数据契约：requirement。
from datetime import date
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.trip import TripPace
from app.schemas.trip import TripBriefPayload


class RequirementParseRequest(BaseModel):
    text: str = Field(default="", max_length=50_000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=3)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        if not value.strip():
            return ""
        return value.strip()

    @model_validator(mode="after")
    def require_text_or_attachment(self) -> Self:
        if not self.text and not self.attachment_ids:
            raise ValueError("text or attachment_ids is required")
        return self


class TripBriefExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str | None = Field(default=None, max_length=120)
    origin: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    budget_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    interests: list[str] = Field(default_factory=list, max_length=20)
    pace: TripPace = "balanced"
    transport_preferences: list[str] = Field(default_factory=list, max_length=20)
    lodging_preferences: list[str] = Field(default_factory=list, max_length=20)
    must_visit: list[str] = Field(default_factory=list, max_length=20)
    avoid: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)

    @field_validator(
        "destination",
        "origin",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "interests",
        "transport_preferences",
        "lodging_preferences",
        "must_visit",
        "avoid",
        "constraints",
    )
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @model_validator(mode="after")
    def validate_partial_date_range(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be on or before end_date")
        return self


class RequirementParseResponse(BaseModel):
    brief: TripBriefPayload | None
    draft: TripBriefExtraction
    missing_fields: list[str]
    questions: list[str]

    @classmethod
    def complete(
        cls,
        brief: TripBriefPayload,
        draft: TripBriefExtraction,
    ) -> Self:
        return cls(brief=brief, draft=draft, missing_fields=[], questions=[])
