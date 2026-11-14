# 文件说明：后端自动化测试：AMap Weather Provider。
from datetime import date

import httpx
import pytest

from app.providers.amap_weather import AmapWeatherProvider
from app.providers.base import ProviderResponseError


async def test_amap_weather_parses_forecast() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/weather/weatherInfo"
        assert request.url.params["extensions"] == "all"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "forecasts": [
                    {
                        "city": "泉州市",
                        "casts": [
                            {
                                "date": "2026-12-20",
                                "dayweather": "晴",
                                "nightweather": "多云",
                                "daytemp": "22",
                                "nighttemp": "13",
                                "daywind": "东北",
                                "daypower": "3",
                            }
                        ],
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapWeatherProvider(
        key="test-key",
        client=client,
        max_retries=0,
    )

    snapshot = await provider.forecast(city="泉州", date=date(2026, 12, 20))

    assert snapshot.provider == "amap-weather"
    assert snapshot.freshness == "live"
    assert snapshot.temperature_max_c == 22
    assert snapshot.temperature_min_c == 13
    assert snapshot.condition == "晴"
    assert snapshot.evidence.source_url is None
    await client.aclose()


async def test_amap_weather_rejects_missing_forecast_date() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "1",
                "forecasts": [{"city": "泉州市", "casts": []}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AmapWeatherProvider(
        key="test-key",
        client=client,
        max_retries=0,
    )

    with pytest.raises(ProviderResponseError):
        await provider.forecast(city="泉州", date=date(2026, 12, 20))
    await client.aclose()
