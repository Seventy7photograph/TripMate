# 文件说明：领域对象：itinerary。
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, cast
from uuid import UUID

from app.domain.location import GeoPoint

SourceFreshness = Literal["live", "cached", "mock", "unknown"]


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    provider: str
    provider_place_id: str | None
    source_url: str | None
    queried_at: datetime
    freshness: SourceFreshness
    confidence: float

    def to_record(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "provider_place_id": self.provider_place_id,
            "source_url": self.source_url,
            "queried_at": self.queried_at.isoformat(),
            "freshness": self.freshness,
            "confidence": self.confidence,
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> "SourceMetadata":
        return cls(
            provider=str(record["provider"]),
            provider_place_id=(
                str(record["provider_place_id"])
                if record.get("provider_place_id") is not None
                else None
            ),
            source_url=(
                str(record["source_url"]) if record.get("source_url") is not None else None
            ),
            queried_at=datetime.fromisoformat(str(record["queried_at"])),
            freshness=cast(SourceFreshness, str(record["freshness"])),
            confidence=float(cast(float | int | str, record["confidence"])),
        )


@dataclass(frozen=True, slots=True)
class ItineraryStop:
    id: UUID
    day_id: UUID
    place_id: str
    place_name: str | None
    start_at: datetime
    duration_minutes: int
    order_index: int
    estimated_cost_minor: int
    location: GeoPoint | None
    source: SourceMetadata
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TripDay:
    id: UUID
    trip_id: UUID
    date: date
    day_index: int
    theme: str | None
    leg_modes: list[str]
    stops: list[ItineraryStop]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Itinerary:
    trip_id: UUID
    version: int
    days: list[TripDay]
