# 文件说明：确定性旅行日期解析，不依赖框架、数据库或 LLM。
"""Parse common Chinese travel date expressions into structured dates."""

import calendar
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

_CN_NUMBER = r"(?:[一二两三四五六七八九]?十[一二两三四五六七八九]?|[一二两三四五六七八九])"
_NUMBER = rf"(?:\d{{1,2}}|{_CN_NUMBER})"
_RANGE_SEPARATOR = r"(?:到|至|—|–|-|~|－)"
_DATE_SUFFIX = r"(?:日|号)"
_FULL_RANGE_RE = re.compile(
    rf"(?P<sy>\d{{4}})年\s*(?P<sm>{_NUMBER})\s*月\s*"
    rf"(?P<sd>{_NUMBER})\s*{_DATE_SUFFIX}\s*{_RANGE_SEPARATOR}\s*"
    rf"(?:(?P<ey>\d{{4}})年\s*)?(?:(?P<em>{_NUMBER})\s*月\s*)?"
    rf"(?P<ed>{_NUMBER})\s*{_DATE_SUFFIX}"
)
_MONTH_DAY_RANGE_RE = re.compile(
    rf"(?P<sm>{_NUMBER})\s*月\s*(?P<sd>{_NUMBER})\s*{_DATE_SUFFIX}\s*"
    rf"{_RANGE_SEPARATOR}\s*(?:(?P<em>{_NUMBER})\s*月\s*)?"
    rf"(?P<ed>{_NUMBER})\s*{_DATE_SUFFIX}"
)
_FULL_DATE_RE = re.compile(
    rf"(?P<year>\d{{4}})年\s*(?P<month>{_NUMBER})\s*月\s*"
    rf"(?P<day>{_NUMBER})\s*{_DATE_SUFFIX}"
)
_MONTH_DAY_RE = re.compile(rf"(?P<month>{_NUMBER})\s*月\s*(?P<day>{_NUMBER})\s*{_DATE_SUFFIX}")
_NEXT_MONTH_DAY_RE = re.compile(rf"下个月\s*(?P<day>{_NUMBER})\s*(?:{_DATE_SUFFIX})?")
_WEEKDAY_RE = re.compile(r"(?P<relative>本|这|下)(?:周|星期)(?P<weekday>[一二三四五六日天])")
_NEXT_WEEK_RE = re.compile(r"下(?:个)?(?:周|星期)(?![一二三四五六日天])")
_WEEKEND_RE = re.compile(r"(?P<relative>本|这|下)周末")
_DAYS_AFTER_RE = re.compile(rf"(?P<days>{_NUMBER})\s*天后")
_WEEK_DURATION_RE = re.compile(rf"(?:大概|约|差不多)?\s*(?P<weeks>{_NUMBER})\s*个?\s*(?:周|星期)")
_DAY_DURATION_RE = re.compile(
    rf"(?<![\d一二两三四五六七八九十月])"
    rf"(?P<days>{_NUMBER})\s*(?:天|日)(?!\s*后)"
    rf"(?:\s*(?P<nights>{_NUMBER})\s*晚)?"
)
_CN_DIGITS = {
    "零": 0,
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
_WEEKDAY_INDEX = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}


@dataclass(frozen=True, slots=True)
class DateResolution:
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    assumptions: list[str] = field(default_factory=list)
    ambiguity_reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def is_ambiguous(self) -> bool:
        return bool(self.ambiguity_reasons)


def resolve_travel_dates(
    message: str,
    today: date,
    history: Sequence[str] = (),
    draft: Mapping[str, object] | None = None,
) -> DateResolution:
    normalized = message.strip()
    if not normalized:
        return _from_context(today=today, history=history, draft=draft)

    range_resolution = _parse_range(normalized, today)
    if range_resolution is not None:
        return range_resolution

    single = _parse_single(normalized, today)
    duration_days = _parse_duration_days(normalized)
    if single is not None:
        if single.start_date is None:
            return single
        end_date = single.end_date
        if end_date is None:
            effective_duration = duration_days or _context_duration(draft)
            if effective_duration is not None:
                end_date = _inclusive_end(single.start_date, effective_duration)
        return _resolution_from_dates(
            start_date=single.start_date,
            end_date=end_date,
            assumptions=single.assumptions,
            confidence=single.confidence,
        )

    if duration_days is not None:
        context = _context_dates(today=today, history=history, draft=draft)
        if context.start_date is not None:
            return _resolution_from_dates(
                start_date=context.start_date,
                end_date=_inclusive_end(context.start_date, duration_days),
                assumptions=[
                    *context.assumptions,
                    "出发日期来自已有规划上下文",
                ],
                confidence=min(context.confidence, 0.9),
            )
        return DateResolution(
            duration_days=duration_days,
            assumptions=[
                f"按包含出发日的 {duration_days} 个自然日计算",
                "尚未确定出发日期",
            ],
            confidence=0.6,
        )

    return _from_context(today=today, history=history, draft=draft)


def _parse_range(message: str, today: date) -> DateResolution | None:
    weekend = _parse_weekend(message, today)
    if weekend is not None:
        return weekend

    full_match = _FULL_RANGE_RE.search(message)
    if full_match is not None:
        start = _safe_date(
            _parse_number(full_match.group("sy")),
            _parse_number(full_match.group("sm")),
            _parse_number(full_match.group("sd")),
        )
        if start is None:
            return _ambiguous("开始日期不是有效日期")
        if start < today:
            return _ambiguous("显式日期已过去，不能自动改到未来")
        end_month = full_match.group("em")
        end_month_number = start.month if end_month is None else _parse_number(end_month)
        end_year = int(full_match.group("ey")) if full_match.group("ey") is not None else start.year
        if (
            full_match.group("ey") is None
            and end_month is not None
            and end_month_number < start.month
        ):
            end_year += 1
        end = _safe_date(
            end_year,
            end_month_number,
            _parse_number(full_match.group("ed")),
        )
        if end is None:
            return _ambiguous("结束日期不是有效日期")
        if end < start:
            return _ambiguous("结束日期早于开始日期，且未明确跨年")
        assumptions = []
        if end_month is None:
            assumptions.append("结束日期沿用开始日期的年月")
        return _resolution_from_dates(
            start_date=start,
            end_date=end,
            assumptions=assumptions,
            confidence=1.0,
        )

    month_day_match = _MONTH_DAY_RANGE_RE.search(message)
    if month_day_match is None:
        return None
    start_month = _parse_number(month_day_match.group("sm"))
    start_day = _parse_number(month_day_match.group("sd"))
    start = _date_in_current_year(today, start_month, start_day)
    if start is None:
        return _ambiguous("未写年份的日期已过去或不是有效日期")
    end_month_group = month_day_match.group("em")
    end_month = start.month if end_month_group is None else _parse_number(end_month_group)
    end_year = start.year
    if end_month_group is not None and end_month < start.month:
        end_year += 1
    end = _safe_date(
        end_year,
        end_month,
        _parse_number(month_day_match.group("ed")),
    )
    if end is None:
        return _ambiguous("结束日期不是有效日期")
    if end < start:
        return _ambiguous("结束日期早于开始日期，且未明确跨月")
    assumptions = [f"未写年份，按 {start.year} 年理解"]
    if end_month_group is None:
        assumptions.append("结束日期沿用开始日期的年月")
    return _resolution_from_dates(
        start_date=start,
        end_date=end,
        assumptions=assumptions,
        confidence=0.93,
    )


def _parse_single(message: str, today: date) -> DateResolution | None:
    full_match = _FULL_DATE_RE.search(message)
    if full_match is not None:
        start = _safe_date(
            int(full_match.group("year")),
            _parse_number(full_match.group("month")),
            _parse_number(full_match.group("day")),
        )
        if start is None:
            return _ambiguous("日期不是有效日期")
        if start < today:
            return _ambiguous("显式日期已过去，不能自动改到未来")
        return _resolution_from_dates(
            start_date=start,
            end_date=None,
            confidence=1.0,
        )

    next_month_match = _NEXT_MONTH_DAY_RE.search(message)
    if next_month_match is not None:
        month = today.month + 1
        year = today.year
        if month == 13:
            month = 1
            year += 1
        start = _safe_date(year, month, _parse_number(next_month_match.group("day")))
        if start is None:
            return _ambiguous("下个月指定日期不是有效日期")
        return _resolution_from_dates(
            start_date=start,
            end_date=None,
            assumptions=[
                f"下个月按 {year}-{month:02d} 理解",
            ],
            confidence=0.96,
        )

    month_day_match = _MONTH_DAY_RE.search(message)
    if month_day_match is not None:
        start = _date_in_current_year(
            today,
            _parse_number(month_day_match.group("month")),
            _parse_number(month_day_match.group("day")),
        )
        if start is None:
            return _ambiguous("未写年份的日期已过去或不是有效日期")
        return _resolution_from_dates(
            start_date=start,
            end_date=None,
            assumptions=[f"未写年份，按 {today.year} 年理解"],
            confidence=0.9,
        )

    relative = _parse_relative_day(message, today)
    if relative is not None:
        return relative

    if _NEXT_WEEK_RE.search(message):
        current_monday = today - timedelta(days=today.weekday())
        return _resolution_from_dates(
            start_date=current_monday + timedelta(days=7),
            end_date=None,
            assumptions=["下个星期按下一周周一开始理解"],
            confidence=0.9,
        )

    weekday = _parse_weekday(message, today)
    if weekday is not None:
        return weekday

    if "月底" in message:
        last_day = calendar.monthrange(today.year, today.month)[1]
        return _resolution_from_dates(
            start_date=date(today.year, today.month, last_day),
            end_date=None,
            assumptions=["月底按当前月份最后一天理解"],
            confidence=0.9,
        )
    return None


def _parse_weekend(message: str, today: date) -> DateResolution | None:
    match = _WEEKEND_RE.search(message)
    if match is None:
        return None
    current_monday = today - timedelta(days=today.weekday())
    if match.group("relative") == "下":
        current_monday += timedelta(days=7)
    start = current_monday + timedelta(days=5)
    end = current_monday + timedelta(days=6)
    return _resolution_from_dates(
        start_date=start,
        end_date=end,
        assumptions=["周末按周六至周日理解"],
        confidence=0.92,
    )


def _parse_relative_day(
    message: str,
    today: date,
) -> DateResolution | None:
    relative_days = {
        "大后天": 3,
        "后天": 2,
        "明天": 1,
        "今天": 0,
    }
    for expression, offset in relative_days.items():
        if expression in message:
            return _resolution_from_dates(
                start_date=today + timedelta(days=offset),
                end_date=None,
                assumptions=[f"以 {today.isoformat()} 为今天解析相对日期"],
                confidence=0.98,
            )
    match = _DAYS_AFTER_RE.search(message)
    if match is None:
        return None
    offset = _parse_number(match.group("days"))
    return _resolution_from_dates(
        start_date=today + timedelta(days=offset),
        end_date=None,
        assumptions=[f"以 {today.isoformat()} 为今天解析相对日期"],
        confidence=0.97,
    )


def _parse_weekday(message: str, today: date) -> DateResolution | None:
    match = _WEEKDAY_RE.search(message)
    if match is None:
        return None
    current_monday = today - timedelta(days=today.weekday())
    if match.group("relative") == "下":
        current_monday += timedelta(days=7)
    target = current_monday + timedelta(days=_WEEKDAY_INDEX[match.group("weekday")])
    if target < today:
        return _ambiguous("本周指定日期已过去，不能自动改到下一周")
    return _resolution_from_dates(
        start_date=target,
        end_date=None,
        confidence=0.92,
    )


def _parse_duration_days(message: str) -> int | None:
    week_match = _WEEK_DURATION_RE.search(message)
    if week_match is not None:
        return _parse_number(week_match.group("weeks")) * 7
    day_match = _DAY_DURATION_RE.search(message)
    if day_match is None:
        return None
    days = _parse_number(day_match.group("days"))
    nights_raw = day_match.group("nights")
    if nights_raw is not None:
        nights = _parse_number(nights_raw)
        if days == nights + 1:
            return days
        return max(days, nights + 1)
    return days


def _context_dates(
    *,
    today: date,
    history: Sequence[str],
    draft: Mapping[str, object] | None,
) -> DateResolution:
    if draft is not None:
        start = _date_value(draft.get("start_date"))
        end = _date_value(draft.get("end_date"))
        if start is not None:
            return _resolution_from_dates(
                start_date=start,
                end_date=end,
                assumptions=["日期来自已有规划草稿"],
                confidence=0.82,
            )
    history_start: date | None = None
    history_end: date | None = None
    history_duration: int | None = None
    assumptions: list[str] = []
    for previous in reversed(history):
        parsed = resolve_travel_dates(previous, today=today)
        if history_duration is None and parsed.duration_days is not None:
            history_duration = parsed.duration_days
        if history_start is None and parsed.start_date is not None:
            history_start = parsed.start_date
            history_end = parsed.end_date
            assumptions = [
                *parsed.assumptions,
                "日期来自最近一轮用户消息",
            ]
        if history_start is not None and history_end is None:
            history_end = parsed.end_date or (
                _inclusive_end(history_start, history_duration)
                if history_duration is not None
                else None
            )
        if history_start is not None and history_end is not None:
            break
    if history_start is not None:
        if history_end is None and history_duration is not None:
            history_end = _inclusive_end(history_start, history_duration)
        return DateResolution(
            start_date=history_start,
            end_date=history_end,
            duration_days=(None if history_end is None else (history_end - history_start).days + 1),
            assumptions=list(dict.fromkeys(assumptions)),
            ambiguity_reasons=[],
            confidence=0.8,
        )
    return DateResolution()


def _from_context(
    *,
    today: date,
    history: Sequence[str],
    draft: Mapping[str, object] | None,
) -> DateResolution:
    return _context_dates(today=today, history=history, draft=draft)


def _context_duration(draft: Mapping[str, object] | None) -> int | None:
    if draft is None:
        return None
    direct = draft.get("duration_days")
    if isinstance(direct, int) and direct > 0:
        return direct
    date_context = draft.get("date_context")
    if isinstance(date_context, Mapping):
        value = date_context.get("duration_days")
        if isinstance(value, int) and value > 0:
            return value
    start = _date_value(draft.get("start_date"))
    end = _date_value(draft.get("end_date"))
    if start is not None and end is not None and end >= start:
        return (end - start).days + 1
    return None


def _date_in_current_year(
    today: date,
    month: int,
    day: int,
) -> date | None:
    candidate = _safe_date(today.year, month, day)
    if candidate is None or candidate < today:
        return None
    return candidate


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_number(raw: str) -> int:
    normalized = raw.strip()
    if normalized.isdigit():
        return int(normalized)
    if normalized == "十":
        return 10
    if "十" in normalized:
        left, _, right = normalized.partition("十")
        tens = _CN_DIGITS.get(left, 1) if left else 1
        units = _CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + units
    return _CN_DIGITS[normalized]


def _inclusive_end(start: date, duration_days: int) -> date:
    return start + timedelta(days=max(duration_days, 1) - 1)


def _resolution_from_dates(
    *,
    start_date: date,
    end_date: date | None,
    assumptions: Sequence[str] = (),
    confidence: float,
) -> DateResolution:
    duration_days = None if end_date is None else max((end_date - start_date).days + 1, 0)
    normalized_assumptions = list(dict.fromkeys(assumptions))
    if duration_days is not None:
        normalized_assumptions = list(
            dict.fromkeys(
                [
                    *normalized_assumptions,
                    f"按包含出发日的 {duration_days} 个自然日计算",
                ]
            )
        )
    return DateResolution(
        start_date=start_date,
        end_date=end_date,
        duration_days=duration_days,
        assumptions=normalized_assumptions,
        confidence=confidence,
    )


def _ambiguous(reason: str) -> DateResolution:
    return DateResolution(
        ambiguity_reasons=[reason],
        confidence=0.0,
    )


def _date_value(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None
