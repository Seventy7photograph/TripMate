# 文件说明：Pydantic 数据契约：place。
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlaceLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    longitude: float
    latitude: float
    coordinate_system: Literal["GCJ-02", "WGS84"]


class PlaceSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_place_id: str | None
    source_url: str | None
    queried_at: datetime
    freshness: Literal["live", "cached", "mock", "unknown"]
    confidence: float


class PlaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_place_id: str
    name: str
    category: str | None
    address: str | None
    location: PlaceLocationResponse | None
    tel: str | None
    opening_hours: list[str]
    source: PlaceSourceResponse
    reference_price: str | None = None


class PlaceSearchResponse(BaseModel):
    provider: str
    profile: str
    cached: bool
    results: list[PlaceResponse]


class GeocodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    longitude: float
    latitude: float
    coordinate_system: Literal["GCJ-02", "WGS84"]


class ProviderStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile: str
    provider: str
    configured: bool
    capabilities: list[str]


class StoredPlaceResponse(PlaceResponse):
    id: UUID
