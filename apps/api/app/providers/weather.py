# 文件说明：外部 Provider 契约：Weather。
from datetime import date as Date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.draft import EvidenceDraft


class WeatherSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    city: str
    date: Date
    condition: str
    temperature_max_c: int | None = None
    temperature_min_c: int | None = None
    precipitation_probability: int | None = Field(default=None, ge=0, le=100)
    humidity_percent: int | None = Field(default=None, ge=0, le=100)
    wind_direction: str | None = None
    wind_power: str | None = None
    freshness: Literal["live", "cached", "unknown"] = "live"
    evidence: EvidenceDraft


class WeatherProvider(Protocol):
    name: str

    async def forecast(
        self,
        *,
        city: str,
        date: Date,
    ) -> WeatherSnapshot: ...


class ElevationProvider(Protocol):
    name: str

    async def get_altitude(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> float | None: ...
