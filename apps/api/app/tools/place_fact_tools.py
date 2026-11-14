# 文件说明：Agent 受控工具：place_fact_tools。
from datetime import date as Date
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.draft import EvidenceDraft
from app.providers.base import PlaceResult, place_to_record
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence


class PlaceFactResolver(Protocol):
    @property
    def name(self) -> str: ...

    async def get(self, provider_place_id: str) -> PlaceResult: ...


class GetPlaceFactsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1, max_length=120)
    date: Date


class PlaceFactOutput(BaseModel):
    place_id: str
    name: str
    date: Date
    opening_hours: list[str]
    opening_hours_status: str
    reference_price: str | None
    ticket_price_status: str
    evidence_ids: list[UUID]


_GET_PLACE_FACTS_SPEC = ToolSpec(
    name="get_place_facts",
    description="Return known opening hours and reference price with evidence.",
    input_model=GetPlaceFactsInput,
    output_model=PlaceFactOutput,
    provider_type="map",
    risk="read",
    timeout_seconds=20.0,
    max_retries=0,
)


class PlaceFactTool:
    name = _GET_PLACE_FACTS_SPEC.name

    def __init__(
        self,
        resolver: PlaceFactResolver,
        context: ToolContext,
    ) -> None:
        self._resolver = resolver
        self._context = context

    async def get_place_facts(
        self,
        place_id: str,
        *,
        date: Date,
    ) -> PlaceFactOutput:
        request = GetPlaceFactsInput(place_id=place_id, date=date)
        return await self._get_facts(self._context, request)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        return await self._get_facts(
            context,
            GetPlaceFactsInput.model_validate(payload),
        )

    async def _get_facts(
        self,
        context: ToolContext,
        request: GetPlaceFactsInput,
    ) -> PlaceFactOutput:
        place = await context.runner.call(
            tool_name=self.name,
            provider=self._resolver.name,
            input_payload=request.model_dump(mode="json"),
            operation=lambda: self._resolver.get(request.place_id),
            timeout_seconds=_GET_PLACE_FACTS_SPEC.timeout_seconds,
        )
        opening_status = "known" if place.opening_hours else "unknown"
        price_status = (
            "known" if place.reference_price is not None else "unknown"
        )
        evidence_ids = [
            await write_evidence(
                context,
                _fact_evidence(
                    place,
                    suffix="opening-hours",
                    value={
                        "date": request.date.isoformat(),
                        "opening_hours": place.opening_hours,
                        "opening_hours_status": opening_status,
                    },
                ),
            ),
            await write_evidence(
                context,
                _fact_evidence(
                    place,
                    suffix="ticket-price",
                    value={
                        "date": request.date.isoformat(),
                        "reference_price": place.reference_price,
                        "ticket_price_status": price_status,
                    },
                ),
            ),
        ]
        return PlaceFactOutput(
            place_id=place.provider_place_id,
            name=place.name,
            date=request.date,
            opening_hours=place.opening_hours,
            opening_hours_status=opening_status,
            reference_price=place.reference_price,
            ticket_price_status=price_status,
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _GET_PLACE_FACTS_SPEC


def _fact_evidence(
    place: PlaceResult,
    *,
    suffix: str,
    value: dict[str, object],
) -> EvidenceDraft:
    return EvidenceDraft(
        fact_type="place_fact",
        provider=place.source.provider,
        provider_record_id=f"{place.provider_place_id}:{suffix}",
        source_url=place.source.source_url,
        fetched_at=place.source.queried_at,
        confidence=place.source.confidence,
        freshness=place.source.freshness,
        value={
            **place_to_record(place),
            **value,
        },
    )
