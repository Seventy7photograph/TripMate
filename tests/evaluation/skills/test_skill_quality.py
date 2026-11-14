# 文件说明：Agent Skill 发布质量评测。

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

CASES_PATH = Path(__file__).with_name("cases.yaml")


@dataclass(frozen=True, slots=True)
class QualityReport:
    case_count: int
    evidence_coverage: float
    unknown_fact_label_rate: float
    invented_price_or_hours_rate: float
    unauthorized_skill_rate: float
    tool_limit_escape_rate: float


def load_evaluation() -> tuple[
    dict[str, float],
    list[dict[str, Any]],
]:
    payload = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return (
        {
            key: float(value)
            for key, value in payload["thresholds"].items()
        },
        list(payload["cases"]),
    )


def build_report(cases: list[dict[str, Any]]) -> QualityReport:
    requested = sum(int(case["observed"]["facts_requested"]) for case in cases)
    evidence = sum(int(case["observed"]["evidence_ids"]) for case in cases)
    unknown = sum(int(case["observed"]["unknown_facts"]) for case in cases)
    labeled = sum(
        int(case["observed"]["unknown_fact_labels"]) for case in cases
    )
    invented = sum(
        int(case["observed"]["invented_price_or_hours"]) for case in cases
    )
    return QualityReport(
        case_count=len(cases),
        evidence_coverage=_ratio(evidence, requested),
        unknown_fact_label_rate=_ratio(labeled, unknown),
        invented_price_or_hours_rate=_ratio(invented, requested),
        unauthorized_skill_rate=_ratio(
            sum(
                bool(case["observed"]["unauthorized_skill"])
                for case in cases
            ),
            len(cases),
        ),
        tool_limit_escape_rate=_ratio(
            sum(
                bool(case["observed"]["tool_limit_escape"])
                for case in cases
            ),
            len(cases),
        ),
    )


def _ratio(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0.0


@pytest.fixture
def report() -> QualityReport:
    _, cases = load_evaluation()
    return build_report(cases)


def test_quality_dataset_covers_release_scenarios() -> None:
    _, cases = load_evaluation()

    assert len(cases) >= 30
    assert {case["category"] for case in cases} == {
        "travel_scenario",
        "prompt_injection",
        "skill_control",
        "mcp_failure",
        "evidence_policy",
    }
    assert {
        case["region_type"] for case in cases
    } >= {"mega_city", "county", "nature", "high_altitude"}
    assert any(int(case["duration_days"]) >= 7 for case in cases)
    assert any(int(case["duration_days"]) <= 3 for case in cases)
    conditions = {
        condition
        for case in cases
        for condition in case["conditions"]
    }
    assert {
        "rain",
        "closure",
        "reservation_required",
        "transit_delay",
        "mcp_timeout",
        "unknown_tool",
    } <= conditions
    traveler_profiles = {
        profile
        for case in cases
        for profile in case["traveler_profile"]
    }
    assert {"elderly", "children", "vegetarian", "allergy"} <= traveler_profiles


def test_evidence_and_skill_quality_thresholds(report: QualityReport) -> None:
    thresholds, _ = load_evaluation()

    assert report.case_count >= 30
    assert report.evidence_coverage >= thresholds["evidence_coverage"]
    assert report.unknown_fact_label_rate == thresholds["unknown_fact_label_rate"]
    assert (
        report.invented_price_or_hours_rate
        < thresholds["invented_price_or_hours_rate"]
    )
    assert report.unauthorized_skill_rate == thresholds["unauthorized_skill_rate"]
    assert report.tool_limit_escape_rate == thresholds["tool_limit_escape_rate"]
