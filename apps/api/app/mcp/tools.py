# 文件说明：将真实 MCP Gateway 结果适配为现有受控 Tool 输出契约。
from datetime import UTC, datetime
from typing import cast

from pydantic import BaseModel

from app.evidence.draft import EvidenceDraft
from app.evidence.models import EvidenceFreshness
from app.mcp.gateway import McpGateway
from app.tools.context import ToolContext
from app.tools.evidence import write_evidence
from app.tools.place_tools import SearchPlacesInput, SearchPlacesOutput
from app.tools.weather_tools import (
    GetWeatherInput,
    WeatherSnapshotOutput,
    WeatherToolOutput,
)


class McpPlaceTool:
    def __init__(self, gateway: McpGateway) -> None:
        self._gateway = gateway

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = SearchPlacesInput.model_validate(payload)
        result = await self._gateway.call_tool(
            context,
            "amap",
            "search_places",
            request.model_dump(mode="json"),
        )
        validated = SearchPlacesOutput.model_validate(result.data)
        if result.fallback_used:
            return validated
        queried_at = datetime.now(UTC)
        return SearchPlacesOutput(
            results=[
                place.model_copy(
                    update={
                        "source": place.source.model_copy(
                            update={
                                "provider": "mcp:amap",
                                "source_url": None,
                                "queried_at": queried_at,
                                "freshness": "unknown",
                                "confidence": min(
                                    place.source.confidence,
                                    0.5,
                                ),
                            }
                        )
                    }
                )
                for place in validated.results
            ]
        )


class McpWeatherTool:
    def __init__(self, gateway: McpGateway) -> None:
        self._gateway = gateway

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = GetWeatherInput.model_validate(payload)
        result = await self._gateway.call_tool(
            context,
            "weather",
            "get_weather",
            request.model_dump(mode="json"),
        )
        if "evidence_id" in result.data:
            return WeatherToolOutput.model_validate(result.data)
        snapshot = WeatherSnapshotOutput.model_validate(result.data).model_copy(
            update={
                "provider": "mcp:weather",
                "city": request.city,
                "date": request.date,
                "freshness": "unknown",
            }
        )
        evidence_id = await write_evidence(
            context,
            EvidenceDraft(
                fact_type="weather",
                provider=snapshot.provider,
                provider_record_id=(
                    f"weather:{snapshot.city}:{snapshot.date.isoformat()}"
                ),
                fetched_at=datetime.now(UTC),
                confidence=0.5,
                freshness=cast(EvidenceFreshness, snapshot.freshness),
                value={
                    "date": snapshot.date.isoformat(),
                    "condition": snapshot.condition,
                    "temperature_max_c": snapshot.temperature_max_c,
                    "temperature_min_c": snapshot.temperature_min_c,
                    "precipitation_probability": (
                        snapshot.precipitation_probability
                    ),
                    "humidity_percent": snapshot.humidity_percent,
                    "wind_direction": snapshot.wind_direction,
                    "wind_power": snapshot.wind_power,
                },
            ),
        )
        return WeatherToolOutput(
            **snapshot.model_dump(),
            evidence_id=evidence_id,
        )
