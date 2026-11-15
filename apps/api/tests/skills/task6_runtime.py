# 文件说明：后端自动化测试辅助：Task 6 Skill 运行时。
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.domain.location import GeoPoint
from app.evidence.draft import EvidenceDraft
from app.providers.base import (
    PlaceQuery,
    PlaceResult,
    RouteRequest,
    RouteResult,
    fresh_source,
)
from app.providers.weather import WeatherSnapshot
from app.skills.executor import SkillContext, SkillExecutor
from app.skills.production import production_skill_handlers
from app.skills.registry import SkillRegistry
from app.tools.altitude_tools import AltitudeTool
from app.tools.base import ToolRunner
from app.tools.context import ToolContext
from app.tools.matrix_tools import MatrixTool
from app.tools.place_fact_tools import PlaceFactTool
from app.tools.place_tools import PlaceTool
from app.tools.registry import ToolRegistry
from app.tools.route_tools import RouteTool
from app.tools.weather_tools import WeatherTool
from tests.tools.external_fact_helpers import MemoryEvidenceWriter


class FakeWeatherProvider:
    name = "amap-weather"

    async def forecast(self, *, city: str, date: date) -> WeatherSnapshot:
        now = datetime.now(UTC)
        return WeatherSnapshot(
            provider=self.name,
            city=city,
            date=date,
            condition="晴",
            temperature_max_c=22,
            temperature_min_c=11,
            precipitation_probability=10,
            humidity_percent=55,
            wind_direction="东北",
            wind_power="3",
            evidence=EvidenceDraft(
                fact_type="weather",
                provider=self.name,
                provider_record_id=f"weather:{city}:{date.isoformat()}",
                fetched_at=now,
                confidence=0.9,
                freshness="live",
                value={"condition": "晴"},
            ),
        )


class FakeElevationProvider:
    name = "open-meteo-elevation"

    async def get_altitude(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> float | None:
        del latitude, longitude
        return 3200


class FakeMapProvider:
    name = "amap"

    async def search_places(self, query: PlaceQuery) -> list[PlaceResult]:
        places = [
            _place("food-1", "开元寺素斋", "餐饮服务", 118.58),
            _place("food-2", "西街小吃", "餐饮服务", 118.59),
            _place("area-1", "钟楼地铁站", "交通设施服务", 118.60),
            _place("area-2", "泉州站", "交通设施服务", 118.61),
        ]
        if "地铁站" in query.keyword:
            places = [
                place
                for place in places
                if place.category == "交通设施服务"
            ]
        elif any(
            term in query.keyword
            for term in ("早餐", "午餐", "晚餐")
        ):
            places = [
                place
                for place in places
                if place.category == "餐饮服务"
            ]
        elif query.types:
            places = [
                place for place in places if place.category == query.types
            ]
        return places[: query.limit]

    async def get_route(self, request: RouteRequest) -> RouteResult:
        del request
        now = datetime.now(UTC)
        return RouteResult(
            distance_m=1200,
            duration_s=900,
            polyline="118.60,24.91;118.61,24.91",
            source=fresh_source(
                provider="amap",
                provider_place_id=None,
                source_url=None,
                freshness="live",
                confidence=0.9,
                queried_at=now,
            ),
        )


class FakePlaceResolver:
    name = "amap"

    def __init__(self) -> None:
        self.places = {
            "food-1": _place("food-1", "开元寺素斋", "餐饮服务", 118.58),
            "food-2": _place("food-2", "西街小吃", "餐饮服务", 118.59),
            "area-1": _place("area-1", "钟楼地铁站", "交通设施服务", 118.60),
            "area-2": _place("area-2", "泉州站", "交通设施服务", 118.61),
        }

    async def get(self, provider_place_id: str) -> PlaceResult:
        return self.places[provider_place_id]


def task6_runtime() -> tuple[
    SkillRegistry,
    ToolRegistry,
    ToolContext,
    SkillExecutor,
    MemoryEvidenceWriter,
]:
    known_tools = {
        "search_places",
        "get_route",
        "calculate_budget",
        "get_authorized_memory_context",
        "get_weather",
        "get_place_facts",
        "get_altitude",
        "get_route_matrix",
        "extract_attachment",
    }
    skills = SkillRegistry(known_tools=known_tools)
    from pathlib import Path

    skills.load(Path(__file__).resolve().parents[4] / "skills")
    context = ToolContext(
        runner=ToolRunner(
            max_calls=20,
            deadline=datetime.now(UTC) + timedelta(seconds=30),
        ),
        allowed_tools=known_tools,
        provider_permissions={"map", "weather", "deterministic", "memory"},
        owner_id=uuid4(),
        evidence_writer=MemoryEvidenceWriter(),
    )
    writer = context.evidence_writer
    assert isinstance(writer, MemoryEvidenceWriter)
    tools = ToolRegistry()
    map_provider = FakeMapProvider()
    route_tool = RouteTool(map_provider, context)
    resolver = FakePlaceResolver()
    registrations = [
        (PlaceTool.spec(), PlaceTool(map_provider, context).invoke),
        (RouteTool.spec(), route_tool.invoke),
        (
            WeatherTool.spec(),
            WeatherTool(
                primary=FakeWeatherProvider(),
                context=context,
            ).invoke,
        ),
        (
            PlaceFactTool.spec(),
            PlaceFactTool(resolver, context).invoke,
        ),
        (
            MatrixTool.spec(),
            MatrixTool(resolver, route_tool, context).invoke,
        ),
        (
            AltitudeTool.spec(),
            AltitudeTool(FakeElevationProvider(), context).invoke,
        ),
    ]
    for spec, handler in registrations:
        tools.register(spec, handler)
    return skills, tools, context, SkillExecutor(), writer


def skill_context(
    tools: ToolRegistry,
    context: ToolContext,
    skill_name: str,
) -> SkillContext:
    handler = production_skill_handlers(tools, context)[skill_name]
    return SkillContext(
        tool_registry=tools,
        tool_context=context,
        handler=handler,
    )


def _place(
    place_id: str,
    name: str,
    category: str,
    longitude: float,
) -> PlaceResult:
    now = datetime.now(UTC)
    return PlaceResult(
        provider_place_id=place_id,
        name=name,
        category=category,
        address="泉州市鲤城区",
        location=GeoPoint(longitude, 24.91),
        tel=None,
        opening_hours=[] if place_id.startswith("food") else ["06:00-23:00"],
        reference_price="人均 40 元" if place_id.startswith("food") else None,
        source=fresh_source(
            provider="amap",
            provider_place_id=place_id,
            source_url=f"https://www.amap.com/place/{place_id}",
            freshness="live",
            confidence=0.9,
            queried_at=now,
        ),
    )
