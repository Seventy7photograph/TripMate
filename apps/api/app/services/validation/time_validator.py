# 文件说明：确定性校验器：time_validator。
from datetime import timedelta

from app.schemas.ai import ItineraryDraftContract, ValidationIssueContract


def validate_time(draft: ItineraryDraftContract) -> list[ValidationIssueContract]:
    issues: list[ValidationIssueContract] = []
    for day in draft.days:
        previous_end = None
        for stop in sorted(day.stops, key=lambda item: item.start_at):
            if stop.start_at.date() != day.date:
                issues.append(
                    ValidationIssueContract(
                        code="invalid_schema",
                        severity="error",
                        path=f"{day.id}.{stop.id}",
                        message="地点时间不在所属日期内",
                    )
                )
            stop_end = stop.start_at + timedelta(minutes=stop.duration_minutes)
            if previous_end is not None and stop.start_at < previous_end:
                issues.append(
                    ValidationIssueContract(
                        code="time_conflict",
                        severity="error",
                        path=f"{day.id}.{stop.id}",
                        message="相邻地点时间重叠",
                        repair_hint="重新安排非锁定地点时间",
                    )
                )
            previous_end = max(previous_end, stop_end) if previous_end else stop_end
    return issues
