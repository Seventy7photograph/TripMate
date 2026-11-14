# 文件说明：Agent 受控工具：nearby_tools。
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.location import CoordinateSystem, GeoPoint
from app.evidence.draft import EvidenceDraft
from app.providers.base import (
    NearbyPlaceProvider,
    PlaceResult,
    ProviderConfigurationError,
    place_to_record,
)
from app.schemas.place import PlaceResponse
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence


class NearbyPointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    coordinate_system: CoordinateSystem = "GCJ-02"


class SearchNearbyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: NearbyPointInput
    radius_m: int = Field(ge=100, le=50_000)
    types: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=10, ge=1, le=25)


class NearbyPlacesOutput(BaseModel):
    results: list[PlaceResponse]
    evidence_ids: list[UUID]


_SEARCH_NEARBY_SPEC = ToolSpec(
    name="search_nearby_places",
    description="Search real POIs around a coordinate with evidence.",
    input_model=SearchNearbyInput,
    output_model=NearbyPlacesOutput,
    provider_type="map",
    risk="read",
    timeout_seconds=20.0,
    max_retries=0,
)


class NearbyTool:
    name = _SEARCH_NEARBY_SPEC.name

    def __init__(
        self,
        provider: NearbyPlaceProvider,
        context: ToolContext,
    ) -> None:
        self._provider = provider
        self._context = context

    async def search_nearby_places(
        self,
        *,
        location: GeoPoint,
        radius_m: int,
        types: list[str],
        limit: int,
    ) -> NearbyPlacesOutput:
        request = SearchNearbyInput(
            location=NearbyPointInput(
                longitude=location.longitude,
                latitude=location.latitude,
                coordinate_system=location.coordinate_system,
            ),
            radius_m=radius_m,
            types=types,
            limit=limit,
        )
        return await self._search(self._context, request, location)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = SearchNearbyInput.model_validate(payload)
        location = GeoPoint(
            longitude=request.location.longitude,
            latitude=request.location.latitude,
            coordinate_system=request.location.coordinate_system,
        )
        return await self._search(context, request, location)

    async def _search(
        self,
        context: ToolContext,
        request: SearchNearbyInput,
        location: GeoPoint,
    ) -> NearbyPlacesOutput:
        if self._provider.name == "mock":
            raise ProviderConfigurationError(
                "nearby search requires a live map provider"
            )
        places = await context.runner.call(
            tool_name=self.name,
            provider=self._provider.name,
            input_payload=request.model_dump(mode="json"),
            operation=lambda: self._provider.search_nearby(
                location=location,
                radius_m=request.radius_m,
                types=request.types,
                limit=request.limit,
            ),
            timeout_seconds=_SEARCH_NEARBY_SPEC.timeout_seconds,
        )
        evidence_ids = [
            await write_evidence(context, _place_evidence(place))
            for place in places
        ]
        return NearbyPlacesOutput(
            results=[PlaceResponse.model_validate(place) for place in places],
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _SEARCH_NEARBY_SPEC


def _place_evidence(place: PlaceResult) -> EvidenceDraft:
    return EvidenceDraft(
        fact_type="place_fact",
        provider=place.source.provider,
        provider_record_id=place.provider_place_id,
        source_url=place.source.source_url,
        fetched_at=place.source.queried_at,
        confidence=place.source.confidence,
        freshness=place.source.freshness,
        value=place_to_record(place),
    )
