# 文件说明：后端自动化测试：规划草稿字段合并优先级。
from datetime import date

from app.domain.planning_merge import merge_planning_draft
from app.domain.transport import TransportSegmentPreference, TransportStrategy
from app.domain.travel_dates import DateResolution
from app.schemas.planning_draft import PlanningDraft
from app.schemas.requirement import TripBriefExtraction


def test_new_message_overrides_previous_field() -> None:
    merged = merge_planning_draft(
        previous=PlanningDraft(destination="西藏", party_size=2),
        extracted=TripBriefExtraction(party_size=1),
        date_resolution=DateResolution(),
    )

    assert merged.destination == "西藏"
    assert merged.party_size == 1


def test_deterministic_dates_override_model_dates() -> None:
    merged = merge_planning_draft(
        previous=PlanningDraft(),
        extracted=TripBriefExtraction(
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 3),
        ),
        date_resolution=DateResolution(
            start_date=date(2026, 12, 12),
            end_date=date(2026, 12, 18),
            duration_days=7,
            assumptions=["按包含出发日的 7 个自然日计算"],
            confidence=0.95,
        ),
    )

    assert merged.start_date == date(2026, 12, 12)
    assert merged.end_date == date(2026, 12, 18)
    assert merged.date_context["duration_days"] == 7
    assert merged.date_context["confidence"] == 0.95


def test_unset_extraction_fields_do_not_erase_existing_preferences() -> None:
    merged = merge_planning_draft(
        previous=PlanningDraft(
            interests=["美食"],
            pace="relaxed",
            lodging_preferences=["地铁附近"],
        ),
        extracted=TripBriefExtraction(party_size=2),
        date_resolution=DateResolution(),
    )

    assert merged.party_size == 2
    assert merged.interests == ["美食"]
    assert merged.pace == "relaxed"
    assert merged.lodging_preferences == ["地铁附近"]


def test_unspecified_transport_does_not_erase_existing_strategy() -> None:
    previous_strategy = TransportStrategy(
        strategy="single",
        segments=[
            TransportSegmentPreference(
                mode="self_drive",
                coverage="whole_trip",
                description="全程自驾",
            )
        ],
    )
    merged = merge_planning_draft(
        previous=PlanningDraft(transport_strategy=previous_strategy),
        extracted=TripBriefExtraction(),
        date_resolution=DateResolution(),
    )

    assert merged.transport_strategy.strategy == "single"
    assert merged.transport_strategy.segments[0].mode == "self_drive"
