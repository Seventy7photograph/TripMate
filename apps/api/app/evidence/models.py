# 文件说明：Evidence 事实层：models。
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EvidenceFactType = Literal[
    "place_fact",
    "weather",
    "transport",
    "lodging_area",
    "meal",
    "safety",
    "altitude",
    "attachment",
]
EvidenceFreshness = Literal["live", "cached", "stale", "mock", "unknown"]


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    trip_id: UUID | None = None
    fact_type: EvidenceFactType
    provider: str = Field(min_length=1, max_length=80)
    provider_record_id: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    fetched_at: datetime
    valid_until: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: EvidenceFreshness
    license_scope: str | None = Field(default=None, max_length=120)
    raw_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    value: dict[str, object]

    @field_validator("provider")
    @classmethod
    def provider_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("provider must not be blank")
        return normalized

    @field_validator("fetched_at", "valid_until")
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validity_must_follow_fetch_time(self) -> "EvidenceRecord":
        if self.valid_until is not None and self.valid_until < self.fetched_at:
            raise ValueError("valid_until must not be earlier than fetched_at")
        return self
