# 文件说明：后端自动化测试：Open-Meteo Provider。
from datetime import date

import httpx

from app.providers.open_meteo import (
    OpenMeteoElevationProvider,
    OpenMeteoWeatherProvider,
)


async def test_open_meteo_weather_resolves_city_and_daily_forecast() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "name": "泉州",
                            "latitude": 24.91,
                            "longitude": 118.58,
                        }
                    ]
                },
            )
        assert request.url.path == "/v1/forecast"
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2026-12-20"],
                    "weather_code": [1],
                    "temperature_2m_max": [23.2],
                    "temperature_2m_min": [12.7],
                    "precipitation_probability_max": [10],
                    "wind_speed_10m_max": [14.5],
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenMeteoWeatherProvider(client=client)

    snapshot = await provider.forecast(
        city="泉州",
        date=date(2026, 12, 20),
    )

    assert snapshot.condition == "大部晴朗"
    assert snapshot.temperature_max_c == 23
    assert snapshot.temperature_min_c == 12
    assert snapshot.precipitation_probability == 10
    assert snapshot.evidence.fact_type == "weather"
    await client.aclose()


async def test_open_meteo_elevation_returns_none_for_empty_values() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/elevation"
        return httpx.Response(200, json={"elevation": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenMeteoElevationProvider(client=client)

    altitude = await provider.get_altitude(
        latitude=29.66,
        longitude=91.14,
    )

    assert altitude is None
    await client.aclose()
