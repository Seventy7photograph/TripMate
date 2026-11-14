# 文件说明：后端自动化测试：test_evidence_freshness。
from datetime import UTC, datetime

import pytest

from app.evidence.freshness import resolve_freshness


@pytest.mark.parametrize(
    ("source_freshness", "valid_until", "expected"),
    [
        ("live", datetime(2026, 11, 14, 10, 0, tzinfo=UTC), "stale"),
        ("cached", datetime(2026, 11, 14, 10, 0, tzinfo=UTC), "stale"),
        ("live", datetime(2026, 11, 14, 11, 0, tzinfo=UTC), "live"),
        ("cached", None, "cached"),
        ("mock", datetime(2026, 11, 14, 10, 0, tzinfo=UTC), "mock"),
        ("unknown", datetime(2026, 11, 14, 10, 0, tzinfo=UTC), "unknown"),
    ],
)
def test_resolve_freshness_applies_validity_without_masking_source_quality(
    source_freshness: str,
    valid_until: datetime | None,
    expected: str,
) -> None:
    now = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)

    assert (
        resolve_freshness(
            source_freshness=source_freshness,  # type: ignore[arg-type]
            valid_until=valid_until,
            now=now,
        )
        == expected
    )
