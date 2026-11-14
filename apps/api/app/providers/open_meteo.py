# 文件说明：外部 Provider 适配：Open-Meteo Weather 与 Elevation。
from datetime import UTC, datetime
from datetime import date as Date
from typing import cast

import httpx

from app.evidence.draft import EvidenceDraft
from app.providers.base import ProviderResponseError, ProviderUnavailableError
from app.providers.weather import WeatherSnapshot

_WEATHER_CODES = {
    0: "晴",
    1: "大部晴朗",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    95: "雷暴",
}


class OpenMeteoWeatherProvider:
    name = "open-meteo"

    def __init__(
        self,
        *,
        forecast_base_url: str = "https://api.open-meteo.com",
        geocoding_base_url: str = "https://geocoding-api.open-meteo.com",
        timeout_seconds: float = 8,
        proxy_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._forecast_base_url = forecast_base_url.rstrip("/")
        self._geocoding_base_url = geocoding_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            proxy=proxy_url,
            follow_redirects=False,
            trust_env=False,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def forecast(self, *, city: str, date: Date) -> WeatherSnapshot:
        geocoding = await self._get_json(
            f"{self._geocoding_base_url}/v1/search",
            {"name": city, "count": 1, "language": "zh", "format": "json"},
        )
        results = cast(list[dict[str, object]], geocoding.get("results", []))
        if not results:
            raise ProviderResponseError("Open-Meteo could not resolve city")
        latitude = float(str(results[0]["latitude"]))
        longitude = float(str(results[0]["longitude"]))
        payload = await self._get_json(
            f"{self._forecast_base_url}/v1/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,wind_speed_10m_max"
                ),
                "timezone": "Asia/Shanghai",
                "start_date": date.isoformat(),
                "end_date": date.isoformat(),
            },
        )
        daily = cast(dict[str, list[object]], payload.get("daily", {}))
        dates = cast(list[object], daily.get("time", []))
        if not dates or str(dates[0]) != date.isoformat():
            raise ProviderResponseError("Open-Meteo has no forecast for date")
        code = _first_int(daily.get("weather_code"))
        condition = _WEATHER_CODES.get(code, "未知天气") if code is not None else "未知天气"
        fetched_at = datetime.now(UTC)
        temperature_max = _first_int(daily.get("temperature_2m_max"))
        temperature_min = _first_int(daily.get("temperature_2m_min"))
        precipitation = _first_int(daily.get("precipitation_probability_max"))
        wind_speed = _first_int(daily.get("wind_speed_10m_max"))
        return WeatherSnapshot(
            provider=self.name,
            city=city,
            date=date,
            condition=condition,
            temperature_max_c=temperature_max,
            temperature_min_c=temperature_min,
            precipitation_probability=precipitation,
            wind_power=f"{wind_speed} km/h" if wind_speed is not None else None,
            evidence=EvidenceDraft(
                fact_type="weather",
                provider=self.name,
                provider_record_id=f"weather:{city}:{date.isoformat()}",
                source_url=None,
                fetched_at=fetched_at,
                confidence=0.82,
                freshness="live",
                value={
                    "date": date.isoformat(),
                    "condition": condition,
                    "temperature_max_c": temperature_max,
                    "temperature_min_c": temperature_min,
                    "precipitation_probability": precipitation,
                },
            ),
        )

    async def _get_json(
        self,
        url: str,
        params: dict[str, str | int | float | bool | None],
    ) -> dict[str, object]:
        try:
            response = await self._client.get(
                url,
                params=params,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Open-Meteo request failed") from exc
        if response.status_code >= 400:
            raise ProviderUnavailableError("Open-Meteo service is unavailable")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderResponseError("Open-Meteo response must be an object")
        return cast(dict[str, object], payload)


class OpenMeteoElevationProvider:
    name = "open-meteo-elevation"

    def __init__(
        self,
        *,
        base_url: str = "https://api.open-meteo.com",
        timeout_seconds: float = 8,
        proxy_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            proxy=proxy_url,
            follow_redirects=False,
            trust_env=False,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_altitude(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> float | None:
        try:
            response = await self._client.get(
                f"{self._base_url}/v1/elevation",
                params={"latitude": latitude, "longitude": longitude},
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                "Open-Meteo elevation request failed"
            ) from exc
        if response.status_code >= 400:
            raise ProviderUnavailableError(
                "Open-Meteo elevation service is unavailable"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Open-Meteo elevation response must be an object"
            )
        elevations = payload.get("elevation")
        if not isinstance(elevations, list) or not elevations:
            return None
        try:
            return float(elevations[0])
        except (TypeError, ValueError):
            return None


def _first_int(values: object) -> int | None:
    if not isinstance(values, list) or not values:
        return None
    try:
        return int(float(str(values[0])))
    except (TypeError, ValueError):
        return None
