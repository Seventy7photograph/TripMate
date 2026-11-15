# 文件说明：Agent 受控工具：route_tools。
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.location import CoordinateSystem
from app.providers.base import (
    GeoPoint,
    MapProvider,
    RouteMode,
    RouteRequest,
    RouteResult,
)
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec


@dataclass(frozen=True, slots=True)
class RouteToolInput:
    origin: GeoPoint
    destination: GeoPoint
    mode: RouteMode
    city: str | None = None


class RoutePointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    coordinate_system: CoordinateSystem = "GCJ-02"


class GetRouteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: RoutePointInput
    destination: RoutePointInput
    mode: RouteMode
    city: str | None = Field(default=None, max_length=100)


class RouteSourceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_place_id: str | None
    source_url: str | None
    queried_at: datetime
    freshness: Literal["live", "cached", "mock", "unknown"]
    confidence: float


class RouteToolOutput(BaseModel):
    distance_m: int
    duration_s: int
    polyline: str | None
    source: RouteSourceOutput


_GET_ROUTE_SPEC = ToolSpec(
    name="get_route",
    description="Calculate a deterministic provider-backed route.",
    input_model=GetRouteInput,
    output_model=RouteToolOutput,
    provider_type="map",
    risk="read",
    timeout_seconds=25.0,
    max_retries=0,
)


class RouteTool:
    name = _GET_ROUTE_SPEC.name

    def __init__(self, provider: MapProvider, context: ToolContext) -> None:
        self._provider = provider
        self._context = context
        self._cache: dict[tuple[object, ...], RouteToolOutput] = {}

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def get(self, request: RouteToolInput) -> RouteToolOutput:
        cache_key = (
            self._provider.name,
            request.origin.longitude,
            request.origin.latitude,
            request.origin.coordinate_system,
            request.destination.longitude,
            request.destination.latitude,
            request.destination.coordinate_system,
            request.mode,
            request.city,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        payload = GetRouteInput(
            origin=RoutePointInput(
                longitude=request.origin.longitude,
                latitude=request.origin.latitude,
                coordinate_system=request.origin.coordinate_system,
            ),
            destination=RoutePointInput(
                longitude=request.destination.longitude,
                latitude=request.destination.latitude,
                coordinate_system=request.destination.coordinate_system,
            ),
            mode=request.mode,
            city=request.city,
        )
        result = await self.invoke(self._context, payload)
        output = RouteToolOutput.model_validate(result)
        self._cache[cache_key] = output
        return output

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = GetRouteInput.model_validate(payload)
        provider_request = RouteRequest(
            origin=GeoPoint(
                longitude=request.origin.longitude,
                latitude=request.origin.latitude,
                coordinate_system=request.origin.coordinate_system,
            ),
            destination=GeoPoint(
                longitude=request.destination.longitude,
                latitude=request.destination.latitude,
                coordinate_system=request.destination.coordinate_system,
            ),
            mode=request.mode,
            city=request.city,
        )
        result = await context.runner.call(
            tool_name=self.name,
            provider=self._provider.name,
            input_payload=request.model_dump(mode="json"),
            operation=lambda: self._provider.get_route(provider_request),
            timeout_seconds=_GET_ROUTE_SPEC.timeout_seconds,
            max_retries=_GET_ROUTE_SPEC.max_retries,
        )
        return _route_output(result)

    @staticmethod
    def spec() -> ToolSpec:
        return _GET_ROUTE_SPEC

    @staticmethod
    def schema() -> dict[str, object]:
        parameters = dict(GetRouteInput.model_json_schema())
        parameters["additionalProperties"] = False
        return {
            "name": _GET_ROUTE_SPEC.name,
            "description": _GET_ROUTE_SPEC.description,
            "parameters": parameters,
        }


def _route_output(result: RouteResult) -> RouteToolOutput:
    return RouteToolOutput(
        distance_m=result.distance_m,
        duration_s=result.duration_s,
        polyline=result.polyline,
        source=RouteSourceOutput.model_validate(result.source),
    )
