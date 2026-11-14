# 文件说明：后端自动化测试：Route Matrix Tool。
from datetime import UTC, datetime

from app.domain.location import GeoPoint
from app.providers.base import PlaceResult, fresh_source
from app.tools.matrix_tools import MatrixTool
from app.tools.route_tools import RouteTool
from tests.tools.external_fact_helpers import evidence_context


class FakePlaceResolver:
    name = "amap"

    def __init__(self) -> None:
        self.places = {
            "a": _place("a", 118.58),
            "b": _place("b", 118.59),
            "c": _place("c", 118.60),
            "missing-coordinate": _place("missing-coordinate", None),
        }

    async def get(self, provider_place_id: str) -> PlaceResult:
        return self.places[provider_place_id]


class CountingMatrixProvider:
    name = "amap"

    def __init__(self) -> None:
        self.calls = 0

    async def get_route(self, request):
        self.calls += 1
        return __import__("app.providers.base", fromlist=["RouteResult"]).RouteResult(
            distance_m=1_200,
            duration_s=900,
            polyline="118.58,24.91;118.59,24.91",
            source=fresh_source(
                provider="amap",
                provider_place_id=None,
                source_url=None,
                freshness="live",
                confidence=0.9,
                queried_at=datetime.now(UTC),
            ),
        )


def _place(place_id: str, longitude: float | None) -> PlaceResult:
    return PlaceResult(
        provider_place_id=place_id,
        name=place_id,
        category=None,
        address=None,
        location=GeoPoint(longitude, 24.91) if longitude is not None else None,
        tel=None,
        opening_hours=[],
        source=fresh_source(
            provider="amap",
            provider_place_id=place_id,
            source_url=None,
            freshness="live",
            confidence=0.9,
            queried_at=datetime.now(UTC),
        ),
    )


async def test_matrix_tool_reuses_route_tool_cache_for_adjacent_pairs() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_route"},
        provider_permissions={"map"},
    )
    provider = CountingMatrixProvider()
    route_tool = RouteTool(provider, context)
    tool = MatrixTool(FakePlaceResolver(), route_tool, context)

    first = await tool.get_route_matrix(["a", "b", "c"], "walking")
    second = await tool.get_route_matrix(["a", "b", "c"], "walking")

    assert len(first.pairs) == 2
    assert first.pairs[0].distance_m == 1_200
    assert provider.calls == 2
    assert context.runner.call_count == 2
    assert second.pairs == first.pairs
    assert len(writer.records) == 2


async def test_matrix_tool_reports_missing_coordinates_without_fake_route() -> None:
    context, _ = evidence_context(
        allowed_tools={"get_route"},
        provider_permissions={"map"},
    )
    route_tool = RouteTool(CountingMatrixProvider(), context)
    tool = MatrixTool(FakePlaceResolver(), route_tool, context)

    result = await tool.get_route_matrix(["a", "missing-coordinate"], "walking")

    assert result.pairs[0].status == "route_unavailable"
    assert "missing-coordinate" in result.missing_place_ids
    assert context.runner.call_count == 0
