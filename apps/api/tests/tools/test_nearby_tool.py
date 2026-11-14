# 文件说明：后端自动化测试：Nearby Tool。
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.location import GeoPoint
from app.providers.base import PlaceResult, fresh_source
from app.tools.nearby_tools import NearbyTool
from tests.tools.external_fact_helpers import evidence_context


class FakeNearbyProvider:
    name = "amap"

    async def search_nearby(
        self,
        *,
        location: GeoPoint,
        radius_m: int,
        types: list[str],
        limit: int,
    ) -> list[PlaceResult]:
        assert location.longitude == 118.58
        assert radius_m == 1_000
        assert types == ["风景名胜"]
        assert limit == 3
        return [
            PlaceResult(
                provider_place_id="nearby-1",
                name="开元寺",
                category="风景名胜",
                address="泉州市鲤城区",
                location=GeoPoint(118.58, 24.91),
                tel=None,
                opening_hours=[],
                source=fresh_source(
                    provider="amap",
                    provider_place_id="nearby-1",
                    source_url="https://www.amap.com/place/nearby-1",
                    freshness="live",
                    confidence=0.95,
                    queried_at=datetime.now(UTC),
                ),
            )
        ]


async def test_nearby_tool_returns_real_pois_with_evidence() -> None:
    context, writer = evidence_context(
        allowed_tools={"search_nearby_places"},
        provider_permissions={"map"},
    )
    tool = NearbyTool(FakeNearbyProvider(), context)

    result = await tool.search_nearby_places(
        location=GeoPoint(118.58, 24.91),
        radius_m=1_000,
        types=["风景名胜"],
        limit=3,
    )

    assert result.results[0].name == "开元寺"
    assert len(result.evidence_ids) == 1
    assert writer.records[result.evidence_ids[0]].fact_type == "place_fact"


async def test_nearby_tool_rejects_out_of_range_radius() -> None:
    context, _ = evidence_context(
        allowed_tools={"search_nearby_places"},
        provider_permissions={"map"},
    )
    tool = NearbyTool(FakeNearbyProvider(), context)

    with pytest.raises(ValidationError):
        await tool.search_nearby_places(
            location=GeoPoint(118.58, 24.91),
            radius_m=50,
            types=["风景名胜"],
            limit=3,
        )
