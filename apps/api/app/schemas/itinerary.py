# 文件说明：Pydantic 数据契约：itinerary。
from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.itinerary import SourceFreshness, SourceMetadata
from app.domain.location import CoordinateSystem, GeoPoint
from app.providers.base import RouteMode


class GeoPointPayload(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    coordinate_system: CoordinateSystem = "GCJ-02"

    def to_domain(self) -> GeoPoint:
        return GeoPoint(
            longitude=self.longitude,
            latitude=self.latitude,
            coordinate_system=self.coordinate_system,
        )


class GeoPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    longitude: float
    latitude: float
    coordinate_system: CoordinateSystem


class SourceMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_place_id: str | None
    source_url: str | None
    queried_at: datetime
    freshness: SourceFreshness
    confidence: float


class SourceMetadataPayload(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    provider_place_id: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=1_000)
    queried_at: datetime
    freshness: SourceFreshness
    confidence: float = Field(ge=0, le=1)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("source_url must use http or https")
        return normalized

    def to_domain(self) -> SourceMetadata:
        return SourceMetadata(
            provider=self.provider,
            provider_place_id=self.provider_place_id,
            source_url=self.source_url,
            queried_at=self.queried_at,
            freshness=self.freshness,
            confidence=self.confidence,
        )


class ItineraryStopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    day_id: UUID
    place_id: str
    place_name: str | None
    start_at: datetime
    duration_minutes: int
    order_index: int
    estimated_cost_minor: int
    location: GeoPointResponse | None
    source: SourceMetadataResponse
    created_at: datetime
    updated_at: datetime


class TripDayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID
    date: date
    day_index: int
    theme: str | None
    leg_modes: list[RouteMode]
    stops: list[ItineraryStopResponse]
    created_at: datetime
    updated_at: datetime


class ItineraryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: UUID
    version: int
    days: list[TripDayResponse]


class TripDayCreateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    date: date
    theme: str | None = Field(default=None, max_length=160)

    @field_validator("theme")
    @classmethod
    def normalize_theme(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ItineraryStopCreateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    place_id: str = Field(min_length=1, max_length=200)
    place_name: str | None = Field(default=None, max_length=200)
    start_at: datetime
    duration_minutes: int = Field(gt=0, le=1440)
    estimated_cost_minor: int = Field(default=0, ge=0)
    location: GeoPointPayload | None = None
    source: SourceMetadataPayload | None = None

    @field_validator("place_id", "place_name")
    @classmethod
    def normalize_place_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("place fields cannot be blank")
        return normalized

    @field_validator("start_at")
    @classmethod
    def normalize_local_datetime(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=None)


class ItineraryStopUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    place_id: str | None = Field(default=None, min_length=1, max_length=200)
    place_name: str | None = Field(default=None, max_length=200)
    start_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    estimated_cost_minor: int | None = Field(default=None, ge=0)
    location: GeoPointPayload | None = None
    source: SourceMetadataPayload | None = None

    @field_validator("place_id", "place_name")
    @classmethod
    def normalize_place_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("place fields cannot be blank")
        return normalized

    @field_validator("start_at")
    @classmethod
    def normalize_local_datetime(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=None) if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not (self.model_fields_set - {"expected_version"}):
            raise ValueError("at least one stop field is required")
        return self


class ReorderStopsRequest(BaseModel):
    expected_version: int = Field(ge=1)
    stop_ids: list[UUID]

    @field_validator("stop_ids")
    @classmethod
    def require_unique_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("stop_ids cannot contain duplicates")
        return values
