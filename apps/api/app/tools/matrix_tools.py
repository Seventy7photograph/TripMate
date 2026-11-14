# 文件说明：Agent 受控工具：matrix_tools。
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.draft import EvidenceDraft
from app.providers.base import PlaceResult, RouteMode
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence
from app.tools.route_tools import RouteTool, RouteToolInput


class MatrixPlaceResolver(Protocol):
    @property
    def name(self) -> str: ...

    async def get(self, provider_place_id: str) -> PlaceResult: ...


class GetRouteMatrixInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place_ids: list[str] = Field(min_length=2, max_length=12)
    mode: RouteMode


class RouteMatrixPair(BaseModel):
    origin_place_id: str
    destination_place_id: str
    mode: RouteMode
    status: str
    distance_m: int | None = None
    duration_s: int | None = None
    evidence_id: UUID | None = None


class RouteMatrixOutput(BaseModel):
    pairs: list[RouteMatrixPair]
    missing_place_ids: list[str]
    evidence_ids: list[UUID]


_GET_ROUTE_MATRIX_SPEC = ToolSpec(
    name="get_route_matrix",
    description="Calculate adjacent route pairs while honoring the ToolRunner budget.",
    input_model=GetRouteMatrixInput,
    output_model=RouteMatrixOutput,
    provider_type="map",
    risk="read",
    timeout_seconds=60.0,
    max_retries=0,
)


class MatrixTool:
    name = _GET_ROUTE_MATRIX_SPEC.name

    def __init__(
        self,
        resolver: MatrixPlaceResolver,
        route_tool: RouteTool,
        context: ToolContext,
    ) -> None:
        self._resolver = resolver
        self._route_tool = route_tool
        self._context = context
        self._evidence_ids: dict[tuple[str, str, str], UUID] = {}

    async def get_route_matrix(
        self,
        place_ids: list[str],
        mode: RouteMode,
    ) -> RouteMatrixOutput:
        request = GetRouteMatrixInput(place_ids=place_ids, mode=mode)
        return await self._matrix(self._context, request)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        return await self._matrix(
            context,
            GetRouteMatrixInput.model_validate(payload),
        )

    async def _matrix(
        self,
        context: ToolContext,
        request: GetRouteMatrixInput,
    ) -> RouteMatrixOutput:
        places: dict[str, PlaceResult] = {}
        missing: list[str] = []
        for place_id in dict.fromkeys(request.place_ids):
            try:
                place = await self._resolver.get(place_id)
            except Exception:
                missing.append(place_id)
                continue
            if place.location is None:
                missing.append(place_id)
                continue
            places[place_id] = place

        pairs: list[RouteMatrixPair] = []
        evidence_ids: list[UUID] = []
        for origin_id, destination_id in zip(
            request.place_ids,
            request.place_ids[1:],
        ):
            origin = places.get(origin_id)
            destination = places.get(destination_id)
            if origin is None or destination is None:
                pairs.append(
                    RouteMatrixPair(
                        origin_place_id=origin_id,
                        destination_place_id=destination_id,
                        mode=request.mode,
                        status="route_unavailable",
                    )
                )
                continue
            origin_location = origin.location
            destination_location = destination.location
            if origin_location is None or destination_location is None:
                continue
            result = await self._route_tool.get(
                RouteToolInput(
                    origin=origin_location,
                    destination=destination_location,
                    mode=request.mode,
                )
            )
            evidence_key = (origin_id, destination_id, request.mode)
            evidence_id = self._evidence_ids.get(evidence_key)
            if evidence_id is None:
                evidence_id = await write_evidence(
                    context,
                    EvidenceDraft(
                        fact_type="transport",
                        provider=result.source.provider,
                        provider_record_id=(
                            f"{origin_id}:{destination_id}:{request.mode}"
                        ),
                        source_url=result.source.source_url,
                        fetched_at=result.source.queried_at,
                        confidence=result.source.confidence,
                        freshness=result.source.freshness,
                        value={
                            "origin_place_id": origin_id,
                            "destination_place_id": destination_id,
                            "mode": request.mode,
                            "distance_m": result.distance_m,
                            "duration_s": result.duration_s,
                        },
                    ),
                )
                self._evidence_ids[evidence_key] = evidence_id
            evidence_ids.append(evidence_id)
            pairs.append(
                RouteMatrixPair(
                    origin_place_id=origin_id,
                    destination_place_id=destination_id,
                    mode=request.mode,
                    status="success",
                    distance_m=result.distance_m,
                    duration_s=result.duration_s,
                    evidence_id=evidence_id,
                )
            )
        return RouteMatrixOutput(
            pairs=pairs,
            missing_place_ids=list(dict.fromkeys(missing)),
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _GET_ROUTE_MATRIX_SPEC
