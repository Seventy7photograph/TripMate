# 文件说明：确定性校验器：source_validator。
from datetime import UTC, datetime, timedelta

from app.schemas.ai import ItineraryDraftContract, ValidationIssueContract


def validate_sources(
    draft: ItineraryDraftContract,
    *,
    now: datetime | None = None,
    max_age_hours: int = 24,
) -> list[ValidationIssueContract]:
    current_time = now or datetime.now(UTC)
    issues: list[ValidationIssueContract] = []
    for day in draft.days:
        for stop in day.stops:
            source = stop.source
            stale = (
                source.freshness == "unknown"
                or current_time - source.queried_at
                > timedelta(hours=max_age_hours)
            )
            if stale:
                issues.append(
                    ValidationIssueContract(
                        code="stale_data",
                        severity="warning",
                        path=f"{day.id}.{stop.id}.source",
                        message="地点数据已过期或来源未知",
                    )
                )
            if source.confidence < 0.5:
                issues.append(
                    ValidationIssueContract(
                        code="stale_data",
                        severity="warning",
                        path=f"{day.id}.{stop.id}.source.confidence",
                        message="地点来源置信度过低",
                    )
                )
    return issues
