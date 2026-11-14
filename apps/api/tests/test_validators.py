# 文件说明：后端自动化测试：test_validators。
from datetime import UTC, date, datetime, timedelta

from app.providers.base import ProviderUnavailableError
from app.schemas.ai import (
    ItineraryDraftContract,
    ItineraryStopContract,
    SourceMetadataContract,
    TripBriefContract,
    TripDayContract,
)
from app.services.validation.budget_validator import validate_budget
from app.services.validation.route_validator import validate_routes
from app.services.validation.source_validator import validate_sources
from app.services.validation.time_validator import validate_time
from app.tools.budget_tools import BudgetToolResult
from app.tools.route_tools import RouteToolInput


def source(
    *,
    provider: str = "amap",
    freshness: str = "live",
    queried_at: datetime | None = None,
) -> SourceMetadataContract:
    return SourceMetadataContract(
        provider=provider,
        provider_place_id="place-1",
        source_url=None,
        queried_at=queried_at or datetime(2026, 11, 14, tzinfo=UTC),
        freshness=freshness,  # type: ignore[arg-type]
        confidence=0.95,
    )


def draft_with_stops(
    stops: list[ItineraryStopContract],
    *,
    budget_minor: int | None = 500_000,
) -> tuple[ItineraryDraftContract, TripBriefContract]:
    brief = TripBriefContract(
        destination="重庆",
        origin="上海",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 1),
        party_size=2,
        budget_minor=budget_minor,
        must_visit=[],
    )
    draft = ItineraryDraftContract(
        trip_id="trip-1",
        version=1,
        days=[
            TripDayContract(
                id="day-1",
                date=date(2026, 12, 1),
                theme="城市初见",
                stops=stops,
            )
        ],
    )
    return draft, brief


def stop(
    *,
    stop_id: str,
    place_id: str,
    start_at: datetime,
    duration_minutes: int = 90,
    cost_minor: int = 10_000,
    metadata: SourceMetadataContract | None = None,
) -> ItineraryStopContract:
    return ItineraryStopContract(
        id=stop_id,
        place_id=place_id,
        place_name=place_id,
        start_at=start_at,
        duration_minutes=duration_minutes,
        estimated_cost_minor=cost_minor,
        source=metadata or source(),
    )


def candidates() -> list[dict[str, object]]:
    return [
        {
            "provider_place_id": "place-1",
            "name": "地点一",
            "location": {
                "longitude": 106.58,
                "latitude": 29.56,
                "coordinate_system": "GCJ-02",
            },
        },
        {
            "provider_place_id": "place-2",
            "name": "地点二",
            "location": {
                "longitude": 106.59,
                "latitude": 29.57,
                "coordinate_system": "GCJ-02",
            },
        },
    ]


class FailingRouteLookup:
    async def get(self, request: RouteToolInput):
        del request
        raise ProviderUnavailableError("upstream unavailable")


class OverBudgetLookup:
    async def calculate(self, request):
        del request
        return BudgetToolResult(
            estimated_minor=600_000,
            remaining_minor=-100_000,
            within_budget=False,
        )


def test_time_validator_reports_overlapping_stops() -> None:
    start = datetime(2026, 12, 1, 9, 0)
    draft, _ = draft_with_stops(
        [
            stop(stop_id="a", place_id="place-1", start_at=start, duration_minutes=120),
            stop(
                stop_id="b",
                place_id="place-2",
                start_at=start + timedelta(minutes=30),
                duration_minutes=90,
            ),
        ]
    )

    issues = validate_time(draft)

    assert [issue.code for issue in issues] == ["time_conflict"]
    assert issues[0].severity == "error"


async def test_route_validator_reports_provider_failure() -> None:
    draft, _ = draft_with_stops(
        [
            stop(
                stop_id="a",
                place_id="place-1",
                start_at=datetime(2026, 12, 1, 9, 0),
            ),
            stop(
                stop_id="b",
                place_id="place-2",
                start_at=datetime(2026, 12, 1, 11, 0),
            ),
        ]
    )

    issues = await validate_routes(
        draft,
        candidates=candidates(),
        route_lookup=FailingRouteLookup(),
    )

    assert [issue.code for issue in issues] == ["route_unavailable"]


async def test_budget_validator_reports_estimated_overage() -> None:
    draft, brief = draft_with_stops(
        [
            stop(
                stop_id="a",
                place_id="place-1",
                start_at=datetime(2026, 12, 1, 9, 0),
                cost_minor=600_000,
            )
        ]
    )

    issues = await validate_budget(
        draft,
        brief=brief,
        budget_lookup=OverBudgetLookup(),
    )

    assert [issue.code for issue in issues] == ["budget_exceeded"]
    assert "1000" in issues[0].message


def test_source_validator_reports_stale_provider_data() -> None:
    draft, _ = draft_with_stops(
        [
            stop(
                stop_id="a",
                place_id="place-1",
                start_at=datetime(2026, 12, 1, 9, 0),
                metadata=source(
                    freshness="cached",
                    queried_at=datetime(2026, 11, 10, tzinfo=UTC),
                ),
            )
        ]
    )

    issues = validate_sources(
        draft,
        now=datetime(2026, 11, 14, tzinfo=UTC),
        max_age_hours=24,
    )

    assert [issue.code for issue in issues] == ["stale_data"]
