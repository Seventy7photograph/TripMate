# 文件说明：Pydantic 数据契约：route。
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.location import CoordinateSystem
from app.providers.base import RouteMode


class RouteCalculateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    stop_ids: list[UUID] = Field(min_length=1)
    mode: RouteMode = "driving"
    modes: list[RouteMode] | None = None

    @field_validator("stop_ids")
    @classmethod
    def unique_stop_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("stop_ids cannot contain duplicates")
        return values

    @model_validator(mode="after")
    def validate_modes(self) -> Self:
        if self.modes is not None and len(self.modes) != max(len(self.stop_ids) - 1, 0):
            raise ValueError("modes must match adjacent stop pairs")
        return self


class RouteSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_place_id: str | None
    source_url: str | None
    queried_at: datetime
    freshness: str
    confidence: float


class RouteLegResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    day_id: UUID
    from_stop_id: UUID
    to_stop_id: UUID
    mode: RouteMode
    distance_m: int
    duration_s: int
    polyline: str | None
    provider: str
    fetched_at: datetime
    source: RouteSourceResponse


class RouteLegErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_stop_id: UUID
    to_stop_id: UUID
    mode: RouteMode
    code: str
    message: str


class RouteCalculationResponse(BaseModel):
    legs: list[RouteLegResponse]
    errors: list[RouteLegErrorResponse]
    modes: list[RouteMode]


class StaticMapRouteModeQuery(BaseModel):
    mode: RouteMode = "driving"
    zoom: int = Field(default=14, ge=3, le=17)
    width: int = Field(default=900, ge=320, le=1024)
    height: int = Field(default=520, ge=240, le=1024)


class CoordinateResponse(BaseModel):
    longitude: float
    latitude: float
    coordinate_system: CoordinateSystem
