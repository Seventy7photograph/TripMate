# 文件说明：后端自动化测试：确定性旅行日期解析。
from datetime import date

import pytest

from app.domain.travel_dates import resolve_travel_dates


@pytest.mark.parametrize(
    ("message", "start", "end"),
    [
        ("2026年12月12日到19日", date(2026, 12, 12), date(2026, 12, 19)),
        (
            "下个月12号出发，大概一星期",
            date(2026, 12, 12),
            date(2026, 12, 18),
        ),
        ("明天出发，玩三天", date(2026, 11, 16), date(2026, 11, 18)),
    ],
)
def test_resolve_common_dates(
    message: str,
    start: date,
    end: date,
) -> None:
    result = resolve_travel_dates(message, today=date(2026, 11, 15))

    assert result.start_date == start
    assert result.end_date == end
    assert result.duration_days == (end - start).days + 1


@pytest.mark.parametrize(
    ("message", "start", "end"),
    [
        (
            "2026年12月12日到2026年12月19日",
            date(2026, 12, 12),
            date(2026, 12, 19),
        ),
        (
            "12月12日到12月19日",
            date(2026, 12, 12),
            date(2026, 12, 19),
        ),
        (
            "十二月十二日到十九日",
            date(2026, 12, 12),
            date(2026, 12, 19),
        ),
        (
            "12月30日到1月2日",
            date(2026, 12, 30),
            date(2027, 1, 2),
        ),
        ("后天出发，玩2天", date(2026, 11, 17), date(2026, 11, 18)),
        ("3天后出发，玩2天", date(2026, 11, 18), date(2026, 11, 19)),
        (
            "下个星期出发，大概一星期",
            date(2026, 11, 16),
            date(2026, 11, 22),
        ),
        (
            "2026年12月12日出发，五天四晚",
            date(2026, 12, 12),
            date(2026, 12, 16),
        ),
        ("月底出发，玩两天", date(2026, 11, 30), date(2026, 12, 1)),
    ],
)
def test_resolve_supported_date_forms(
    message: str,
    start: date,
    end: date,
) -> None:
    result = resolve_travel_dates(message, today=date(2026, 11, 15))

    assert result.start_date == start
    assert result.end_date == end


@pytest.mark.parametrize(
    ("message", "start", "end"),
    [
        ("本周日出发", date(2026, 11, 15), None),
        ("下周一出发", date(2026, 11, 16), None),
        (
            "下周末出发",
            date(2026, 11, 21),
            date(2026, 11, 22),
        ),
    ],
)
def test_resolve_week_expressions(
    message: str,
    start: date,
    end: date | None,
) -> None:
    result = resolve_travel_dates(message, today=date(2026, 11, 15))

    assert result.start_date == start
    assert result.end_date == end


def test_explicit_return_date_overrides_duration() -> None:
    result = resolve_travel_dates(
        "12月12日到19日，玩三天",
        today=date(2026, 11, 15),
    )

    assert result.start_date == date(2026, 12, 12)
    assert result.end_date == date(2026, 12, 19)
    assert result.duration_days == 8


def test_duration_continues_from_existing_draft() -> None:
    result = resolve_travel_dates(
        "大概一星期",
        today=date(2026, 11, 15),
        draft={"start_date": "2026-12-12"},
    )

    assert result.start_date == date(2026, 12, 12)
    assert result.end_date == date(2026, 12, 18)


def test_duration_continues_from_recent_history() -> None:
    result = resolve_travel_dates(
        "玩三天",
        today=date(2026, 11, 15),
        history=("2026年12月12日出发",),
    )

    assert result.start_date == date(2026, 12, 12)
    assert result.end_date == date(2026, 12, 14)


def test_history_combines_start_date_and_duration_across_turns() -> None:
    result = resolve_travel_dates(
        "这个时间昆明有没有海鸥",
        today=date(2026, 11, 15),
        history=(
            "我想去云南玩一个星期，帮我规划一下",
            "下个星期出发，我自己一个人",
        ),
    )

    assert result.start_date == date(2026, 11, 16)
    assert result.end_date == date(2026, 11, 22)


@pytest.mark.parametrize(
    "message",
    [
        "12月12日到5日",
        "10月1日到10月3日",
        "2026年2月30日出发",
        "2025年12月12日出发",
        "2025年12月12日到2025年12月14日",
    ],
)
def test_ambiguous_or_invalid_dates_are_not_guessed(message: str) -> None:
    result = resolve_travel_dates(message, today=date(2026, 11, 15))

    assert result.start_date is None
    assert result.end_date is None
    assert result.ambiguity_reasons
