# 文件说明：结构化旅行交通策略与确定性规范化。
"""Normalize readable Chinese transport preferences into typed segments."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TransportMode = Literal[
    "self_drive",
    "rental_car",
    "taxi",
    "public_transit",
    "walking",
    "cycling",
    "high_speed_rail",
    "train",
    "flight",
    "ferry",
    "chartered_car",
    "mixed",
]
TransportCoverage = Literal[
    "whole_trip",
    "intercity",
    "destination_local",
    "specific_days",
    "partial",
]
TransportStrategyKind = Literal["single", "mixed", "unspecified"]

_MODE_TERMS: tuple[tuple[TransportMode, tuple[str, ...]], ...] = (
    ("self_drive", ("自驾", "开车", "驾车")),
    ("rental_car", ("租车",)),
    ("taxi", ("打车", "出租车", "网约车", "滴滴")),
    ("public_transit", ("公共交通", "公共汽车", "公交", "地铁")),
    ("walking", ("步行", "走路")),
    ("cycling", ("骑行", "自行车")),
    ("high_speed_rail", ("高铁", "动车")),
    ("train", ("火车", "铁路")),
    ("flight", ("飞机", "航班", "机票")),
    ("ferry", ("轮渡", "坐船")),
    ("chartered_car", ("包车",)),
)
_MODE_DESCRIPTIONS = {
    "self_drive": "自驾",
    "rental_car": "租车",
    "taxi": "打车",
    "public_transit": "公共交通",
    "walking": "步行",
    "cycling": "骑行",
    "high_speed_rail": "高铁",
    "train": "火车",
    "flight": "飞机",
    "ferry": "轮渡",
    "chartered_car": "包车",
    "mixed": "混合交通",
}
_NEGATED_SELF_DRIVE_RE = re.compile(r"(?:不|不再|取消)(?:全程)?(?:自驾|开车|驾车)")
_DAY_RE = re.compile(r"第(?P<day>\d{1,2}|[一二两三四五六七八九十]+)天")
_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


class TransportSegmentPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TransportMode
    coverage: TransportCoverage = "whole_trip"
    days: list[int] | None = Field(default=None, max_length=20)
    parking_required: bool | None = None
    description: str = Field(min_length=1, max_length=200)

    @field_validator("days")
    @classmethod
    def normalize_days(cls, values: list[int] | None) -> list[int] | None:
        if values is None:
            return None
        normalized = sorted({value for value in values if value >= 1})
        return normalized or None


class TransportStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: TransportStrategyKind = "unspecified"
    segments: list[TransportSegmentPreference] = Field(
        default_factory=list,
        max_length=6,
    )
    constraints: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("constraints")
    @classmethod
    def normalize_constraints(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def normalize_transport_strategy(message: str) -> TransportStrategy:
    normalized = message.strip()
    if not normalized:
        return TransportStrategy()

    matches: list[tuple[int, TransportMode, str]] = []
    for mode, terms in _MODE_TERMS:
        if mode == "self_drive" and _NEGATED_SELF_DRIVE_RE.search(normalized):
            continue
        found = _first_term_match(normalized, terms)
        if found is not None:
            matches.append((found[0], mode, found[1]))
    matches.sort(key=lambda item: item[0])
    if not matches:
        return TransportStrategy()

    days = _extract_days(normalized)
    segments = [
        _segment_for_mode(
            mode=mode,
            term=term,
            message=normalized,
            days=days,
            mode_count=len(matches),
        )
        for _, mode, term in matches
    ]
    constraints = _extract_constraints(normalized)
    return TransportStrategy(
        strategy="single" if len(segments) == 1 else "mixed",
        segments=segments,
        constraints=constraints,
    )


def transport_preferences_for(strategy: TransportStrategy) -> list[str]:
    return [segment.description for segment in strategy.segments]


def _first_term_match(message: str, terms: tuple[str, ...]) -> tuple[int, str] | None:
    candidates = [(message.find(term), term) for term in terms if message.find(term) >= 0]
    return min(candidates) if candidates else None


def _segment_for_mode(
    *,
    mode: TransportMode,
    term: str,
    message: str,
    days: list[int],
    mode_count: int,
) -> TransportSegmentPreference:
    coverage = _coverage_for_mode(
        mode=mode,
        term=term,
        message=message,
        days=days,
        mode_count=mode_count,
    )
    return TransportSegmentPreference(
        mode=mode,
        coverage=coverage,
        days=days if coverage == "specific_days" else None,
        parking_required=_parking_requirement(mode, message),
        description=_description_for_mode(mode, coverage, term),
    )


def _coverage_for_mode(
    *,
    mode: TransportMode,
    term: str,
    message: str,
    days: list[int],
    mode_count: int,
) -> TransportCoverage:
    if mode in {"self_drive", "rental_car"} and days:
        return "specific_days"
    if mode == "self_drive" and any(label in message for label in ("城市间", "城际", "跨城")):
        return "intercity"
    if mode in {"high_speed_rail", "train", "flight", "ferry"}:
        return "intercity"
    if "全程" in message:
        return "whole_trip"
    if any(label in message for label in ("市内", "当地", "到了目的地", "目的地内")):
        return "destination_local"
    if any(label in message for label in ("部分", "其他公共交通")):
        return "partial"
    if mode_count > 1 and mode not in {"self_drive"}:
        return "destination_local"
    return "whole_trip"


def _parking_requirement(
    mode: TransportMode,
    message: str,
) -> bool | None:
    if mode not in {"self_drive", "rental_car"}:
        return None
    if any(term in message for term in ("不需要停车", "不用停车")):
        return False
    if any(term in message for term in ("需要停车", "必须停车", "停车位")):
        return True
    return None


def _description_for_mode(
    mode: TransportMode,
    coverage: TransportCoverage,
    term: str,
) -> str:
    coverage_labels = {
        "whole_trip": "全程",
        "intercity": "城市间",
        "destination_local": "目的地内",
        "specific_days": "指定日期",
        "partial": "部分路段",
    }
    return f"{coverage_labels[coverage]}{_MODE_DESCRIPTIONS.get(mode, term)}"


def _extract_days(message: str) -> list[int]:
    return sorted({_parse_number(match.group("day")) for match in _DAY_RE.finditer(message)})


def _parse_number(raw: str) -> int:
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if "十" in raw:
        left, _, right = raw.partition("十")
        tens = _CN_DIGITS.get(left, 1) if left else 1
        units = _CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + units
    return _CN_DIGITS[raw]


def _extract_constraints(message: str) -> list[str]:
    labels = (
        "不走高速",
        "避免堵车",
        "少走路",
        "晕车",
        "带老人",
        "带孩子",
        "尽量夜间不驾驶",
    )
    return [label for label in labels if label in message]
