# 文件说明：后端自动化测试：Evidence 行程验证。
from datetime import UTC, date, datetime
from uuid import uuid4

from app.evidence.models import EvidenceRecord
from app.schemas.ai import DayPlanContract, ItineraryDraftContract
from app.services.evidence_validation_service import EvidenceValidationService


def _record(
    evidence_id,
    *,
    valid_until=None,
    fetched_at=None,
    provider_record_id=None,
    value=None,
) -> EvidenceRecord:
    now = fetched_at or datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
    return EvidenceRecord(
        id=evidence_id,
        owner_id=uuid4(),
        fact_type="weather",
        provider="amap-weather",
        provider_record_id=provider_record_id or f"weather-{evidence_id}",
        fetched_at=now,
        valid_until=valid_until,
        confidence=0.9,
        freshness="live",
        value=value or {"summary": "晴"},
    )


def _draft(evidence_ids: list[str]) -> ItineraryDraftContract:
    return ItineraryDraftContract(
        trip_id="trip-1",
        version=1,
        days=[
            DayPlanContract(
                id="day-1",
                date=date(2026, 12, 20),
                stops=[],
                weather={
                    "status": "known",
                    "summary": "晴",
                    "clothing_advice": [],
                    "risk": "low",
                    "evidence_ids": evidence_ids,
                },
                evidence_ids=evidence_ids,
            )
        ],
    )


def test_unknown_evidence_id_is_rejected_as_missing() -> None:
    service = EvidenceValidationService()

    report = service.validate(_draft(["ev-missing"]), records=[])

    assert any(issue.code == "missing" for issue in report.issues)
    assert report.verified_count == 0


def test_stale_evidence_is_reported() -> None:
    evidence_id = uuid4()
    record = _record(
        evidence_id,
        valid_until=datetime(2026, 11, 15, 7, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 11, 15, 6, 0, tzinfo=UTC),
    )
    service = EvidenceValidationService()

    report = service.validate(
        _draft([str(evidence_id)]),
        records=[record],
        now=datetime(2026, 11, 15, 8, 0, tzinfo=UTC),
    )

    assert any(issue.code == "stale" for issue in report.issues)


def test_fresh_evidence_passes_validation() -> None:
    evidence_id = uuid4()
    record = _record(
        evidence_id,
        valid_until=datetime(2026, 11, 15, 9, 0, tzinfo=UTC),
    )
    service = EvidenceValidationService()

    report = service.validate(
        _draft([str(evidence_id)]),
        records=[record],
        now=datetime(2026, 11, 15, 8, 0, tzinfo=UTC),
    )

    assert report.issues == []
    assert report.verified_count == 1


def test_conflicting_values_from_same_provider_record_are_reported() -> None:
    first_id = uuid4()
    second_id = uuid4()
    records = [
        _record(
            first_id,
            provider_record_id="same-provider-record",
            value={"summary": "晴"},
        ),
        _record(
            second_id,
            provider_record_id="same-provider-record",
            value={"summary": "暴雨"},
        ),
    ]

    report = EvidenceValidationService().validate(
        _draft([str(first_id), str(second_id)]),
        records=records,
        now=datetime(2026, 11, 15, 8, 0, tzinfo=UTC),
    )

    assert any(issue.code == "conflict" for issue in report.issues)


def test_daily_summary_without_evidence_is_unsupported() -> None:
    draft = _draft([])
    draft.days[0].daily_summary = "当日步行游览古城。"

    report = EvidenceValidationService().validate(draft, records=[])

    assert any(
        issue.code == "unsupported_claim"
        for issue in report.issues
    )
