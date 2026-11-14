# 文件说明：AI Agent：fake_planner。
from datetime import UTC, date, datetime, time, timedelta

from app.schemas.ai import (
    DayPlanContract,
    ItineraryDraftContract,
    ItineraryStopContract,
    SourceMetadataContract,
    TripBriefContract,
)

_FIXED_QUERIED_AT = datetime(2026, 11, 13, tzinfo=UTC)


class FakePlanner:
    """Deterministic planner used to exercise the full planning contract."""

    def plan(
        self,
        *,
        trip_id: str,
        version: int,
        brief: TripBriefContract,
    ) -> ItineraryDraftContract:
        days: list[DayPlanContract] = []
        current = brief.start_date
        day_index = 1
        while current <= brief.end_date:
            stops = [
                self._stop(
                    day_index=day_index,
                    stop_index=1,
                    day_date=current,
                    start_time=time(9, 0),
                    name=self._primary_name(brief, day_index),
                    cost_minor=5_000,
                ),
                self._stop(
                    day_index=day_index,
                    stop_index=2,
                    day_date=current,
                    start_time=time(14, 0),
                    name=f"{brief.destination}城市漫步",
                    cost_minor=8_000,
                ),
            ]
            days.append(
                DayPlanContract(
                    id=f"day-{day_index}",
                    date=current,
                    theme=self._theme(day_index),
                    stops=stops,
                )
            )
            current += timedelta(days=1)
            day_index += 1

        return ItineraryDraftContract(
            trip_id=trip_id,
            version=version,
            days=days,
            validation_summary=[],
        )

    @staticmethod
    def _primary_name(brief: TripBriefContract, day_index: int) -> str:
        if day_index == 1 and brief.must_visit:
            return brief.must_visit[0]
        return f"{brief.destination}城市地标"

    @staticmethod
    def _theme(day_index: int) -> str:
        themes = [
            "抵达与城市初识",
            "城市文化与街区",
            "在地体验与返程",
        ]
        return themes[min(day_index - 1, len(themes) - 1)]

    @staticmethod
    def _stop(
        *,
        day_index: int,
        stop_index: int,
        day_date: date,
        start_time: time,
        name: str,
        cost_minor: int,
    ) -> ItineraryStopContract:
        place_id = f"mock-day-{day_index}-place-{stop_index}"
        return ItineraryStopContract(
            id=f"day-{day_index}-stop-{stop_index}",
            place_id=place_id,
            place_name=name,
            start_at=datetime.combine(day_date, start_time),
            duration_minutes=90,
            estimated_cost_minor=cost_minor,
            source=SourceMetadataContract(
                provider="mock",
                provider_place_id=place_id,
                source_url=None,
                queried_at=_FIXED_QUERIED_AT,
                freshness="mock",
                confidence=1.0,
            ),
        )
