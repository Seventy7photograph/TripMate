# 文件说明：后端自动化测试：旅行意图确定性语义规则。
import pytest

from app.domain.travel_intent import (
    extract_trip_destination,
    is_explicit_trip_plan_request,
)


@pytest.mark.parametrize(
    ("message", "destination"),
    [
        ("帮我规划一次广州一日游，citywalk", "广州"),
        ("我想去广州一日游", "广州"),
        ("周末去广州 citywalk", "广州"),
        ("广州城市漫步怎么安排", "广州"),
    ],
)
def test_extract_trip_destination_from_short_trip_phrases(
    message: str,
    destination: str,
) -> None:
    assert extract_trip_destination(message) == destination
    assert is_explicit_trip_plan_request(message) is True


def test_explicit_trip_plan_request_rejects_non_travel_planning() -> None:
    assert is_explicit_trip_plan_request("帮我规划一个 Python 学习路线") is False
