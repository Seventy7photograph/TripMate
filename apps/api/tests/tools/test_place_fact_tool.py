# 文件说明：后端自动化测试：Place Fact Tool。
from datetime import UTC, date, datetime

from app.domain.location import GeoPoint
from app.providers.base import PlaceResult, fresh_source
from app.tools.place_fact_tools import PlaceFactTool
from tests.tools.external_fact_helpers import evidence_context


class FakePlaceResolver:
    name = "amap"

    def __init__(self, *, known: bool) -> None:
        self.known = known

    async def get(self, provider_place_id: str) -> PlaceResult:
        return PlaceResult(
            provider_place_id=provider_place_id,
            name="泉州开元寺",
            category="风景名胜",
            address="泉州市鲤城区",
            location=GeoPoint(118.58, 24.91),
            tel=None,
            opening_hours=["08:00-17:30"] if self.known else [],
            reference_price="40元" if self.known else None,
            source=fresh_source(
                provider="amap",
                provider_place_id=provider_place_id,
                source_url="https://www.amap.com/place/place-1",
                freshness="live",
                confidence=0.95,
                queried_at=datetime.now(UTC),
            ),
        )


async def test_place_fact_tool_marks_known_fields() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_place_facts"},
        provider_permissions={"map"},
    )
    tool = PlaceFactTool(FakePlaceResolver(known=True), context)

    result = await tool.get_place_facts(
        "place-1",
        date=date(2026, 12, 20),
    )

    assert result.opening_hours_status == "known"
    assert result.ticket_price_status == "known"
    assert len(result.evidence_ids) == 2
    assert len(writer.records) == 2


async def test_place_fact_tool_marks_missing_fields_unknown() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_place_facts"},
        provider_permissions={"map"},
    )
    tool = PlaceFactTool(FakePlaceResolver(known=False), context)

    result = await tool.get_place_facts(
        "place-1",
        date=date(2026, 12, 20),
    )

    assert result.opening_hours_status == "unknown"
    assert result.ticket_price_status == "unknown"
    assert result.opening_hours == []
    assert result.reference_price is None
    assert len(writer.records) == 2
