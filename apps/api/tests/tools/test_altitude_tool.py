# 文件说明：后端自动化测试：Altitude Tool。
from app.tools.altitude_tools import AltitudeTool
from tests.tools.external_fact_helpers import evidence_context


class FakeAltitudeProvider:
    name = "open-meteo-elevation"

    def __init__(self, altitude_m: float | None) -> None:
        self.altitude_m = altitude_m

    async def get_altitude(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> float | None:
        assert latitude == 29.66
        assert longitude == 91.14
        return self.altitude_m


async def test_altitude_tool_records_altitude_evidence() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_altitude"},
        provider_permissions={"weather"},
    )
    tool = AltitudeTool(FakeAltitudeProvider(3650), context)

    result = await tool.get_altitude(latitude=29.66, longitude=91.14)

    assert result.altitude_m == 3650
    assert result.status == "known"
    assert writer.records[result.evidence_id].fact_type == "altitude"


async def test_altitude_tool_marks_missing_value_unknown() -> None:
    context, writer = evidence_context(
        allowed_tools={"get_altitude"},
        provider_permissions={"weather"},
    )
    tool = AltitudeTool(FakeAltitudeProvider(None), context)

    result = await tool.get_altitude(latitude=29.66, longitude=91.14)

    assert result.altitude_m is None
    assert result.status == "unknown"
    assert result.freshness == "unknown"
    assert writer.records[result.evidence_id].freshness == "unknown"
