# 文件说明：Agent 受控工具：weather_tools。
from datetime import date as Date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.providers.amap_weather import AmapWeatherProvider
from app.providers.base import ProviderConfigurationError, ProviderError
from app.providers.open_meteo import OpenMeteoWeatherProvider
from app.providers.weather import WeatherProvider, WeatherSnapshot
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.evidence import write_evidence


class GetWeatherInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(min_length=1, max_length=120)
    date: Date


class WeatherToolOutput(BaseModel):
    provider: str
    city: str
    date: Date
    condition: str
    temperature_max_c: int | None
    temperature_min_c: int | None
    precipitation_probability: int | None
    humidity_percent: int | None
    wind_direction: str | None
    wind_power: str | None
    freshness: str
    evidence_id: UUID


class WeatherSnapshotOutput(BaseModel):
    provider: str
    city: str
    date: Date
    condition: str
    temperature_max_c: int | None
    temperature_min_c: int | None
    precipitation_probability: int | None
    humidity_percent: int | None
    wind_direction: str | None
    wind_power: str | None
    freshness: str


_GET_WEATHER_SPEC = ToolSpec(
    name="get_weather",
    description="Fetch a provider-backed weather snapshot for a city and date.",
    input_model=GetWeatherInput,
    output_model=WeatherToolOutput,
    provider_type="weather",
    risk="read",
    timeout_seconds=20.0,
    max_retries=0,
)


class WeatherTool:
    name = _GET_WEATHER_SPEC.name

    def __init__(
        self,
        *,
        primary: WeatherProvider,
        context: ToolContext,
        fallback: WeatherProvider | None = None,
    ) -> None:
        self._primary = primary
        self._context = context
        self._fallback = fallback

    @property
    def primary_provider_name(self) -> str:
        return self._primary.name

    @property
    def fallback_provider_name(self) -> str | None:
        return self._fallback.name if self._fallback is not None else None

    async def get_weather(self, *, city: str, date: Date) -> WeatherToolOutput:
        request = GetWeatherInput(city=city, date=date)
        return await self._get_weather(self._context, request)

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        request = GetWeatherInput.model_validate(payload)
        return await self._get_weather(context, request)

    async def _get_weather(
        self,
        context: ToolContext,
        request: GetWeatherInput,
    ) -> WeatherToolOutput:
        try:
            snapshot = await self._forecast(context, self._primary, request)
        except ProviderError:
            if self._fallback is None:
                raise
            snapshot = await self._forecast(context, self._fallback, request)
        evidence_id = await write_evidence(context, snapshot.evidence)
        return WeatherToolOutput(
            **snapshot.model_dump(exclude={"evidence"}),
            evidence_id=evidence_id,
        )

    async def close(self) -> None:
        seen: set[int] = set()
        for provider in (self._primary, self._fallback):
            if provider is None or id(provider) in seen:
                continue
            seen.add(id(provider))
            close = getattr(provider, "close", None)
            if close is not None:
                await close()

    async def _forecast(
        self,
        context: ToolContext,
        provider: WeatherProvider,
        request: GetWeatherInput,
    ) -> WeatherSnapshot:
        return await context.runner.call(
            tool_name=self.name,
            provider=provider.name,
            input_payload=request.model_dump(mode="json"),
            operation=lambda: provider.forecast(
                city=request.city,
                date=request.date,
            ),
            timeout_seconds=_GET_WEATHER_SPEC.timeout_seconds,
            max_retries=_GET_WEATHER_SPEC.max_retries,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _GET_WEATHER_SPEC


def create_weather_tool(
    settings: Settings,
    context: ToolContext,
) -> WeatherTool:
    fallback = (
        OpenMeteoWeatherProvider(
            forecast_base_url=settings.open_meteo_base_url,
            geocoding_base_url=settings.open_meteo_geocoding_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            proxy_url=_proxy_url(settings),
        )
        if settings.weather_fallback_enabled
        else None
    )
    if (
        settings.effective_map_provider_profile == "live"
        and settings.amap_web_service_key is not None
    ):
        primary: WeatherProvider = AmapWeatherProvider(
            key=settings.amap_web_service_key.get_secret_value(),
            base_url=settings.amap_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
            proxy_url=_proxy_url(settings),
        )
    else:
        if fallback is None:
            raise ProviderConfigurationError(
                "weather provider is not configured"
            )
        primary = fallback
        fallback = None
    return WeatherTool(
        primary=primary,
        fallback=fallback,
        context=context,
    )


def _proxy_url(settings: Settings) -> str | None:
    return (
        settings.outbound_proxy_url.get_secret_value()
        if settings.outbound_proxy_url is not None
        else None
    )
