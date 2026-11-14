# 文件说明：后端自动化测试：Weather Tool。
from datetime import UTC, date, datetime
from uuid import uuid4

from app.core.config import Settings
from app.providers.base import ProviderUnavailableError
from app.providers.weather import WeatherSnapshot
from app.tools.weather_tools import WeatherTool, create_weather_tool
from tests.tools.external_fact_helpers import evidence_context


def snapshot(provider: str) -> WeatherSnapshot:
    now = datetime.now(UTC)
    return WeatherSnapshot(
        provider=provider,
        city="泉州",
        date=date(2026, 12, 20),
        condition="晴",
        temperature_max_c=22,
        temperature_min_c=13,
        precipitation_probability=10,
        humidity_percent=60,
        wind_direction="东北",
        wind_power="3",
        freshness="live",
        evidence={
            "provider": provider,
            "provider_record_id": "weather:泉州:2026-12-20",
            "source_url": None,
            "fetched_at": now,
            "freshness": "live",
            "confidence": 0.9,
            "fact_type": "weather",
            "value": {"condition": "晴"},
        },
    )


class FakeWeatherProvider:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail

    async def forecast(self, *, city: str, date: date) -> WeatherSnapshot:
        del city, date
        if self.fail:
            raise ProviderUnavailableError("weather unavailable")
        return snapshot(self.name)


async def test_weather_tool_falls_back_and_persists_evidence() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_weather"},
        provider_permissions={"weather"},
    )
    tool = WeatherTool(
        primary=FakeWeatherProvider("amap-weather", fail=True),
        context=context,
        fallback=FakeWeatherProvider("open-meteo"),
    )

    result = await tool.get_weather(city="泉州", date=date(2026, 12, 20))

    assert result.provider == "open-meteo"
    assert result.evidence_id
    assert writer.records[result.evidence_id].fact_type == "weather"
    assert context.runner.call_count == 2


async def test_weather_tool_requires_owner_scoped_evidence_writer() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_weather"},
        provider_permissions={"weather"},
    )
    context = context.__class__(
        runner=context.runner,
        allowed_tools=context.allowed_tools,
        provider_permissions=context.provider_permissions,
        owner_id=uuid4(),
        evidence_writer=None,
    )
    tool = WeatherTool(
        primary=FakeWeatherProvider("open-meteo"),
        context=context,
    )

    try:
        await tool.get_weather(city="泉州", date=date(2026, 12, 20))
    except RuntimeError as exc:
        assert "evidence writer" in str(exc)
    else:
        raise AssertionError("missing evidence writer must fail closed")
    assert writer.records == {}


def test_weather_factory_reuses_amap_key_for_weather_api() -> None:
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="live",
        amap_web_service_key="shared-amap-key",
        weather_fallback_enabled=True,
    )
    context, _ = evidence_context(
        allowed_tools={"get_weather"},
        provider_permissions={"weather"},
    )

    tool = create_weather_tool(settings, context)

    assert tool.primary_provider_name == "amap-weather"
    assert tool.fallback_provider_name == "open-meteo"
