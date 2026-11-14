# 文件说明：后端自动化测试：Place Detail Tool。
from datetime import UTC, datetime

from app.domain.location import GeoPoint
from app.providers.base import PlaceResult, fresh_source
from app.tools.place_detail_tools import PlaceDetailTool
from tests.tools.external_fact_helpers import evidence_context


class FakePlaceResolver:
    name = "amap"

    async def get(self, provider_place_id: str) -> PlaceResult:
        assert provider_place_id == "place-1"
        return PlaceResult(
            provider_place_id="place-1",
            name="开元寺",
            category="风景名胜",
            address="泉州市鲤城区西街",
            location=GeoPoint(118.58, 24.91),
            tel="0595-1234567",
            opening_hours=["08:00-17:30"],
            reference_price="免费",
            source=fresh_source(
                provider="amap",
                provider_place_id="place-1",
                source_url="https://www.amap.com/place/place-1",
                freshness="live",
                confidence=0.95,
                queried_at=datetime.now(UTC),
            ),
        )


async def test_place_detail_tool_returns_traceable_detail() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_place_detail"},
        provider_permissions={"map"},
    )
    tool = PlaceDetailTool(FakePlaceResolver(), context)

    result = await tool.get_place_detail("place-1")

    assert result.name == "开元寺"
    assert result.opening_hours == ["08:00-17:30"]
    assert result.reference_price == "免费"
    assert result.evidence_id
    assert writer.records[result.evidence_id].provider_record_id == "place-1"
