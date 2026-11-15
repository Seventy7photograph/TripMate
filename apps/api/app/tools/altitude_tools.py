# 文件说明：Agent 受控工具：altitude_tools。
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.evidence.draft import EvidenceDraft
from app.providers.open_meteo import OpenMeteoElevationProvider
from app.providers.weather import ElevationProvider
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence


class GetAltitudeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class AltitudeOutput(BaseModel):
    altitude_m: float | None
    provider: str
    fetched_at: datetime
    freshness: str
    status: str
    evidence_id: UUID


_GET_ALTITUDE_SPEC = ToolSpec(
    name="get_altitude",
    description="Fetch provider-backed altitude evidence without medical advice.",
    input_model=GetAltitudeInput,
    output_model=AltitudeOutput,
    provider_type="weather",
    risk="read",
    timeout_seconds=15.0,
    max_retries=0,
)


class AltitudeTool:
    name = _GET_ALTITUDE_SPEC.name

    def __init__(
        self,
        provider: ElevationProvider,
        context: ToolContext,
    ) -> None:
        self._provider = provider
        self._context = context

    async def get_altitude(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> AltitudeOutput:
        request = GetAltitudeInput(
            latitude=latitude,
            longitude=longitude,
        )
        return await self._altitude(self._context, request)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        return await self._altitude(
            context,
            GetAltitudeInput.model_validate(payload),
        )

    async def _altitude(
        self,
        context: ToolContext,
        request: GetAltitudeInput,
    ) -> AltitudeOutput:
        altitude_m = await context.runner.call(
            tool_name=self.name,
            provider=self._provider.name,
            input_payload=request.model_dump(mode="json"),
            operation=lambda: self._provider.get_altitude(
                latitude=request.latitude,
                longitude=request.longitude,
            ),
            timeout_seconds=_GET_ALTITUDE_SPEC.timeout_seconds,
        )
        fetched_at = datetime.now(UTC)
        status = "known" if altitude_m is not None else "unknown"
        freshness: Literal["live", "unknown"] = (
            "live" if altitude_m is not None else "unknown"
        )
        evidence_id = await write_evidence(
            context,
            EvidenceDraft(
                fact_type="altitude",
                provider=self._provider.name,
                provider_record_id=(
                    f"altitude:{request.latitude}:{request.longitude}"
                ),
                source_url=None,
                fetched_at=fetched_at,
                confidence=0.9 if altitude_m is not None else 0.0,
                freshness=freshness,
                value={
                    "altitude_m": altitude_m,
                    "latitude": request.latitude,
                    "longitude": request.longitude,
                    "status": status,
                },
            ),
        )
        return AltitudeOutput(
            altitude_m=altitude_m,
            provider=self._provider.name,
            fetched_at=fetched_at,
            freshness=freshness,
            status=status,
            evidence_id=evidence_id,
        )

    async def close(self) -> None:
        close = getattr(self._provider, "close", None)
        if close is not None:
            await close()

    @staticmethod
    def spec() -> ToolSpec:
        return _GET_ALTITUDE_SPEC


def create_altitude_tool(
    settings: Settings,
    context: ToolContext,
) -> AltitudeTool:
    return AltitudeTool(
        OpenMeteoElevationProvider(
            base_url=settings.open_meteo_elevation_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            proxy_url=(
                settings.outbound_proxy_url.get_secret_value()
                if settings.outbound_proxy_url is not None
                else None
            ),
        ),
        context,
    )
