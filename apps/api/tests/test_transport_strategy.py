# 文件说明：后端自动化测试：结构化交通策略解析。
import pytest

from app.domain.transport import normalize_transport_strategy


@pytest.mark.parametrize(
    ("message", "strategy", "mode", "coverage"),
    [
        ("全程自驾", "single", "self_drive", "whole_trip"),
        (
            "城市间自驾，到了市内坐地铁和走路",
            "mixed",
            "self_drive",
            "intercity",
        ),
        (
            "只有第二天自驾，其他公共交通",
            "mixed",
            "self_drive",
            "specific_days",
        ),
    ],
)
def test_transport_strategy(
    message: str,
    strategy: str,
    mode: str,
    coverage: str,
) -> None:
    result = normalize_transport_strategy(message)

    assert result.strategy == strategy
    assert result.segments[0].mode == mode
    assert result.segments[0].coverage == coverage


def test_mixed_transport_preserves_each_stated_mode() -> None:
    result = normalize_transport_strategy("城市间高铁，到目的地包车，市内地铁和步行")

    assert result.strategy == "mixed"
    assert [segment.mode for segment in result.segments] == [
        "high_speed_rail",
        "chartered_car",
        "public_transit",
        "walking",
    ]
    assert result.segments[0].coverage == "intercity"
    assert result.segments[1].coverage == "destination_local"


def test_selected_day_transport_records_day_indexes() -> None:
    result = normalize_transport_strategy("只有第二天和第四天自驾，其他公共交通")

    assert result.segments[0].days == [2, 4]
    assert result.segments[0].parking_required is None


def test_negative_self_drive_phrase_does_not_create_driving_segment() -> None:
    result = normalize_transport_strategy("不开车，全程坐高铁")

    assert [segment.mode for segment in result.segments] == ["high_speed_rail"]
    assert result.strategy == "single"


def test_destination_rental_car_is_local_coverage() -> None:
    result = normalize_transport_strategy("坐高铁过去，到了当地租车")

    assert [segment.mode for segment in result.segments] == [
        "high_speed_rail",
        "rental_car",
    ]
    assert result.segments[1].coverage == "destination_local"


def test_no_transport_preference_remains_unspecified() -> None:
    result = normalize_transport_strategy("去成都吃火锅")

    assert result.strategy == "unspecified"
    assert result.segments == []
