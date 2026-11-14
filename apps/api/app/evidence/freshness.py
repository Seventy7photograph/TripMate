# 文件说明：Evidence 事实层：freshness。
from datetime import UTC, datetime

from app.evidence.models import EvidenceFreshness


def resolve_freshness(
    *,
    source_freshness: EvidenceFreshness,
    valid_until: datetime | None,
    now: datetime,
) -> EvidenceFreshness:
    normalized_now = _require_aware(now, field_name="now")
    if source_freshness == "mock":
        return "mock"
    if source_freshness == "unknown":
        return "unknown"
    if valid_until is not None:
        normalized_valid_until = _require_aware(valid_until, field_name="valid_until")
        if normalized_valid_until <= normalized_now:
            return "stale"
    return source_freshness


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)
