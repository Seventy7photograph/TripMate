# 文件说明：Agent 受控工具：place_detail_tools。
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.draft import EvidenceDraft
from app.providers.base import PlaceResult, place_to_record
from app.schemas.place import PlaceLocationResponse, PlaceSourceResponse
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence


class PlaceResolver(Protocol):
    @property
    def name(self) -> str: ...

    async def get(self, provider_place_id: str) -> PlaceResult: ...


class PlaceDetailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1, max_length=120)


class PlaceDetailOutput(BaseModel):
    place_id: str
    name: str
    category: str | None
    address: str | None
    location: PlaceLocationResponse | None
    tel: str | None
    opening_hours: list[str]
    opening_hours_status: str
    reference_price: str | None
    ticket_price_status: str
    source: PlaceSourceResponse
    evidence_id: UUID


_GET_PLACE_DETAIL_SPEC = ToolSpec(
    name="get_place_detail",
    description="Fetch provider-backed place detail and persist evidence.",
    input_model=PlaceDetailInput,
    output_model=PlaceDetailOutput,
    provider_type="map",
    risk="read",
    timeout_seconds=20.0,
    max_retries=0,
)


class PlaceDetailTool:
    name = _GET_PLACE_DETAIL_SPEC.name

    def __init__(
        self,
        resolver: PlaceResolver,
        context: ToolContext,
    ) -> None:
        self._resolver = resolver
        self._context = context

    async def get_place_detail(self, place_id: str) -> PlaceDetailOutput:
        request = PlaceDetailInput(place_id=place_id)
        return await self._get_detail(self._context, request)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        return await self._get_detail(
            context,
            PlaceDetailInput.model_validate(payload),
        )

    async def _get_detail(
        self,
        context: ToolContext,
        request: PlaceDetailInput,
    ) -> PlaceDetailOutput:
        place = await context.runner.call(
            tool_name=self.name,
            provider=self._resolver.name,
            input_payload=request.model_dump(mode="json"),
            operation=lambda: self._resolver.get(request.place_id),
            timeout_seconds=_GET_PLACE_DETAIL_SPEC.timeout_seconds,
        )
        evidence_id = await write_evidence(
            context,
            _detail_evidence(place),
        )
        return PlaceDetailOutput(
            place_id=place.provider_place_id,
            name=place.name,
            category=place.category,
            address=place.address,
            location=(
                PlaceLocationResponse.model_validate(place.location)
                if place.location is not None
                else None
            ),
            tel=place.tel,
            opening_hours=place.opening_hours,
            opening_hours_status="known" if place.opening_hours else "unknown",
            reference_price=place.reference_price,
            ticket_price_status=(
                "known" if place.reference_price is not None else "unknown"
            ),
            source=PlaceSourceResponse.model_validate(place.source),
            evidence_id=evidence_id,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _GET_PLACE_DETAIL_SPEC


def _detail_evidence(place: PlaceResult) -> EvidenceDraft:
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
