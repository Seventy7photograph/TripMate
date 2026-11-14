# 文件说明：业务服务：富行程 Evidence 验证。
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.freshness import resolve_freshness
from app.evidence.models import EvidenceRecord
from app.schemas.ai import (
    DayPlanContract,
    ItineraryDraftContract,
    ValidationIssueContract,
)

EvidenceValidationCode = Literal["missing", "stale", "conflict", "unsupported_claim"]
ValidateEvidenceIds = Callable[[list[str], str], None]
AddEvidenceIssue = Callable[[EvidenceValidationCode, str, str], None]


class EvidenceValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: EvidenceValidationCode
    path: str
    message: str


class EvidenceValidationReport(BaseModel):
    issues: list[EvidenceValidationIssue] = Field(default_factory=list)
    verified_count: int = 0

    def as_validation_issues(self) -> list[ValidationIssueContract]:
        mapping = {
            "missing": ("evidence_missing", "error"),
            "stale": ("evidence_stale", "warning"),
            "conflict": ("evidence_conflict", "error"),
            "unsupported_claim": ("unsupported_claim", "error"),
        }
        return [
            ValidationIssueContract(
                code=mapping[issue.code][0],  # type: ignore[arg-type]
                severity=mapping[issue.code][1],  # type: ignore[arg-type]
                path=issue.path,
                message=issue.message,
                repair_hint="刷新或补充对应 Evidence 后再生成该字段。",
            )
            for issue in self.issues
        ]


class EvidenceValidationService:
    def validate(
        self,
        draft: ItineraryDraftContract,
        *,
        records: list[EvidenceRecord],
        now: datetime | None = None,
    ) -> EvidenceValidationReport:
        current = now or datetime.now(UTC)
        records_by_id = {str(record.id): record for record in records}
        issues: list[EvidenceValidationIssue] = []
        seen_issues: set[tuple[str, str]] = set()
        valid_ids: set[str] = set()
        referenced_ids: set[str] = set()

        def add_issue(
            code: EvidenceValidationCode,
            path: str,
            message: str,
        ) -> None:
            key = (code, path)
            if key in seen_issues:
                return
            seen_issues.add(key)
            issues.append(
                EvidenceValidationIssue(
                    code=code,
                    path=path,
                    message=message,
                )
            )

        def validate_ids(ids: list[str], path: str) -> None:
            for evidence_id in ids:
                referenced_ids.add(evidence_id)
                record = records_by_id.get(evidence_id)
                if record is None:
                    add_issue(
                        "missing",
                        path,
                        f"Evidence {evidence_id} 不存在。",
                    )
                    continue
                freshness = resolve_freshness(
                    source_freshness=record.freshness,
                    valid_until=record.valid_until,
                    now=current,
                )
                if freshness == "stale":
                    add_issue(
                        "stale",
                        path,
                        f"Evidence {evidence_id} 已过期。",
                    )
                    continue
                valid_ids.add(evidence_id)

        for day_index, day in enumerate(draft.days):
            self._validate_day(
                day,
                path=f"days.{day_index}",
                validate_ids=validate_ids,
                add_issue=add_issue,
            )

        grouped: dict[str, list[EvidenceRecord]] = {}
        for evidence_id in referenced_ids:
            record = records_by_id.get(evidence_id)
            if record is None or not record.provider_record_id:
                continue
            grouped.setdefault(record.provider_record_id, []).append(record)
        for provider_record_id, grouped_records in grouped.items():
            values = {
                repr(record.value)
                for record in grouped_records
            }
            if len(values) > 1:
                add_issue(
                    "conflict",
                    f"evidence.{provider_record_id}",
                    "同一 Provider 记录对应的 Evidence 值冲突。",
                )

        return EvidenceValidationReport(
            issues=issues,
            verified_count=len(valid_ids),
        )

    @staticmethod
    def _validate_day(
        day: DayPlanContract,
        *,
        path: str,
        validate_ids: ValidateEvidenceIds,
        add_issue: AddEvidenceIssue,
    ) -> None:
        validate_ids(day.evidence_ids, f"{path}.evidence_ids")
        if day.weather.status == "known":
            if not day.weather.evidence_ids:
                add_issue(
                    "missing",
                    f"{path}.weather",
                    "已确认天气缺少 Evidence ID。",
                )
            validate_ids(
                day.weather.evidence_ids,
                f"{path}.weather.evidence_ids",
            )
        for meal_index, meal in enumerate(day.meals):
            if meal.status == "known" and not meal.evidence_ids:
                add_issue(
                    "missing",
                    f"{path}.meals.{meal_index}",
                    "已确认餐饮信息缺少 Evidence ID。",
                )
            validate_ids(
                meal.evidence_ids,
                f"{path}.meals.{meal_index}.evidence_ids",
            )
        for transport_index, transport in enumerate(day.transport):
            validate_ids(
                transport.evidence_ids,
                f"{path}.transport.{transport_index}.evidence_ids",
            )
        if day.lodging_area.status == "known" and not day.lodging_area.evidence_ids:
            add_issue(
                "missing",
                f"{path}.lodging_area",
                "已确认住宿区域缺少 Evidence ID。",
            )
        validate_ids(
            day.lodging_area.evidence_ids,
            f"{path}.lodging_area.evidence_ids",
        )
        validate_ids(
            day.safety.evidence_ids,
            f"{path}.safety.evidence_ids",
        )
        if day.daily_summary and not day.evidence_ids:
            add_issue(
                "unsupported_claim",
                f"{path}.daily_summary",
                "每日摘要包含未引用 Evidence 的说明。",
            )
