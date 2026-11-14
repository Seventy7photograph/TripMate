# 文件说明：后端自动化测试：test_bounded_replan。
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from app.agents.itinerary_composer import ComposerResult
from app.graph.travel_graph import GraphLimits, TravelGraph
from app.providers.mock_map import MockMapProvider
from app.schemas.ai import (
    ItineraryDraftContract,
    ItineraryStopContract,
    SourceMetadataContract,
    TripBriefContract,
    TripDayContract,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def brief_for_destination(*, lock_all: bool = False) -> TripBriefContract:
    payload = json.loads(
        (FIXTURES / "trip_briefs/chongqing-full.json").read_text(encoding="utf-8")
    )
    payload["start_date"] = "2026-12-01"
    payload["end_date"] = "2026-12-01"
    if lock_all:
        payload["must_visit"] = ["洪崖洞民俗风貌区", "解放碑步行街"]
    return TripBriefContract.model_validate(payload)


class OverlapComposer:
    provider_name = "test"
    model_name = "overlap-composer"

    def __init__(self) -> None:
        self.calls = 0

    async def compose(
        self,
        *,
        trip_id: str,
        version: int,
        brief: TripBriefContract,
        candidates: list[dict[str, object]],
    ) -> ComposerResult:
        self.calls += 1
        first = candidates[0]
        second = candidates[1]
        del brief
        starts = datetime(2026, 12, 1, 9, 0)
        stops = [
            ItineraryStopContract(
                id="stop-1",
                place_id=str(first["provider_place_id"]),
                place_name=str(first["name"]),
                start_at=starts,
                duration_minutes=120,
                estimated_cost_minor=10_000,
                source=SourceMetadataContract.model_validate(first["source"]),
            ),
            ItineraryStopContract(
                id="stop-2",
                place_id=str(second["provider_place_id"]),
                place_name=str(second["name"]),
                start_at=starts + timedelta(minutes=30),
                duration_minutes=90,
                estimated_cost_minor=10_000,
                source=SourceMetadataContract.model_validate(second["source"]),
            ),
        ]
        return ComposerResult(
            draft=ItineraryDraftContract(
                trip_id=trip_id,
                version=version,
                days=[
                    TripDayContract(
                        id="day-1",
                        date=date(2026, 12, 1),
                        theme="测试日",
                        stops=stops,
                    )
                ],
            ),
            input_tokens=10,
            output_tokens=10,
            latency_ms=1,
            model_name=self.model_name,
            provider_name=self.provider_name,
        )


async def test_unlocked_time_conflict_is_repaired_deterministically() -> None:
    composer = OverlapComposer()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=composer,
        limits=GraphLimits(max_loops=2),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_for_destination(),
        brief_confirmed=True,
    )

    assert outcome.status == "completed"
    assert composer.calls == 1
    assert outcome.state["loop_count"] == 1
    assert outcome.issues == []
    assert any(event.stage == "repair" for event in outcome.events)


async def test_locked_overlap_returns_partial_after_repair_limit() -> None:
    composer = OverlapComposer()
    graph = TravelGraph(
        map_provider=MockMapProvider(),
        composer=composer,
        limits=GraphLimits(max_loops=2),
    )

    outcome = await graph.run(
        trip_id="trip-1",
        version=1,
        brief=brief_for_destination(lock_all=True),
        brief_confirmed=True,
    )

    assert outcome.status == "partial"
    assert outcome.draft is not None
    assert outcome.state["loop_count"] == 2
    assert any(issue.code == "time_conflict" for issue in outcome.issues)
    assert outcome.events[-1].status == "partial"
