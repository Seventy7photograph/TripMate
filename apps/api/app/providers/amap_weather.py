# 文件说明：外部 Provider 适配：AMap Weather。
from datetime import UTC, datetime
from datetime import date as Date
from typing import cast

from app.evidence.draft import EvidenceDraft
from app.providers.amap import AmapMapProvider
from app.providers.base import ProviderResponseError
from app.providers.weather import WeatherSnapshot


class AmapWeatherProvider(AmapMapProvider):
    name = "amap-weather"

    async def forecast(self, *, city: str, date: Date) -> WeatherSnapshot:
        payload = await self._request(
            "/v3/weather/weatherInfo",
            {
                "city": city,
                "extensions": "all",
            },
        )
        forecasts = cast(list[dict[str, object]], payload.get("forecasts", []))
        if not forecasts:
            raise ProviderResponseError("AMap weather returned no forecast")
        casts = cast(list[dict[str, object]], forecasts[0].get("casts", []))
        selected = next(
            (
                item
                for item in casts
                if str(item.get("date")) == date.isoformat()
            ),
            None,
        )
        if selected is None:
            raise ProviderResponseError("AMap weather has no forecast for date")
        fetched_at = datetime.now(UTC)
        condition = str(selected.get("dayweather") or "unknown")
        return WeatherSnapshot(
            provider=self.name,
            city=str(forecasts[0].get("city") or city),
            date=date,
            condition=condition,
            temperature_max_c=_optional_int(selected.get("daytemp")),
            temperature_min_c=_optional_int(selected.get("nighttemp")),
            wind_direction=_optional_text(selected.get("daywind")),
            wind_power=_optional_text(selected.get("daypower")),
            evidence=EvidenceDraft(
                fact_type="weather",
                provider=self.name,
                provider_record_id=f"weather:{city}:{date.isoformat()}",
                source_url=None,
                fetched_at=fetched_at,
                confidence=0.9,
                freshness="live",
                value={
                    "date": date.isoformat(),
                    "condition": condition,
                    "temperature_max_c": _optional_int(selected.get("daytemp")),
                    "temperature_min_c": _optional_int(selected.get("nighttemp")),
                    "wind_direction": _optional_text(selected.get("daywind")),
                    "wind_power": _optional_text(selected.get("daypower")),
                },
            ),
        )


def _optional_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
