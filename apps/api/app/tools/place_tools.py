# 文件说明：Agent 受控工具：place_tools。
from pydantic import BaseModel, ConfigDict, Field

from app.providers.base import MapProvider, PlaceQuery, PlaceResult
from app.schemas.place import PlaceResponse
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec


class SearchPlacesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    types: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class SearchPlacesOutput(BaseModel):
    results: list[PlaceResponse]


_SEARCH_PLACES_SPEC = ToolSpec(
    name="search_places",
    description="Search provider-backed places by keyword and city.",
    input_model=SearchPlacesInput,
    output_model=SearchPlacesOutput,
    provider_type="map",
    risk="read",
    timeout_seconds=20.0,
    max_retries=0,
)


class PlaceTool:
    name = _SEARCH_PLACES_SPEC.name

    def __init__(self, provider: MapProvider, context: ToolContext) -> None:
        self._provider = provider
        self._context = context

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def search(self, query: PlaceQuery) -> SearchPlacesOutput:
        payload = SearchPlacesInput(
            keyword=query.keyword,
            city=query.city,
            types=query.types,
            limit=query.limit,
        )
        result = await self.invoke(self._context, payload)
        return SearchPlacesOutput.model_validate(result)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = SearchPlacesInput.model_validate(payload)
        results = await context.runner.call(
            tool_name=self.name,
            provider=self._provider.name,
            input_payload=request.model_dump(),
            operation=lambda: self._provider.search_places(
                PlaceQuery(
                    keyword=request.keyword,
                    city=request.city,
                    types=request.types,
                    limit=request.limit,
                )
            ),
            timeout_seconds=_SEARCH_PLACES_SPEC.timeout_seconds,
            max_retries=_SEARCH_PLACES_SPEC.max_retries,
        )
        return SearchPlacesOutput(
            results=[_place_response(place) for place in results],
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _SEARCH_PLACES_SPEC

    @staticmethod
    def schema() -> dict[str, object]:
        parameters = dict(SearchPlacesInput.model_json_schema())
        parameters["additionalProperties"] = False
        return {
            "name": _SEARCH_PLACES_SPEC.name,
            "description": _SEARCH_PLACES_SPEC.description,
            "parameters": parameters,
        }


def _place_response(place: PlaceResult) -> PlaceResponse:
    return PlaceResponse.model_validate(place)
