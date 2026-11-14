# 文件说明：业务服务：itinerary_service。
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.itinerary import Itinerary, ItineraryStop, SourceMetadata, TripDay
from app.domain.location import GeoPoint
from app.domain.trip import Trip, TripBrief
from app.models.trip import Trip as TripModel
from app.repositories.itinerary_repository import ItineraryRepository
from app.services.version_service import VersionService, VersionTripNotFoundError


class ItineraryNotFoundError(Exception):
    pass


class InvalidItineraryError(Exception):
    pass


class DayAlreadyExistsError(Exception):
    pass


class ItineraryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._itinerary = ItineraryRepository(session)
        self._versions = VersionService(session)

    async def get(self, *, owner_id: UUID, trip_id: UUID) -> Itinerary:
        trip = await self._require_trip(owner_id=owner_id, trip_id=trip_id)
        days = await self._itinerary.list_days(trip_id=trip.id)
        return Itinerary(trip_id=trip.id, version=trip.version, days=days)

    async def create_day(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
        day_date: date,
        theme: str | None,
    ) -> TripDay:
        locked_trip = await self._lock_trip(
            owner_id=owner_id,
            trip_id=trip_id,
            expected_version=expected_version,
        )
        brief = TripBrief.from_record(locked_trip.brief)
        if not brief.start_date <= day_date <= brief.end_date:
            raise InvalidItineraryError("day date must be within the trip range")
        if await self._itinerary.has_day(trip_id=locked_trip.id, day_date=day_date):
            raise DayAlreadyExistsError

        day_index = (day_date - brief.start_date).days + 1
        try:
            day = await self._itinerary.create_day(
                trip_id=locked_trip.id,
                day_date=day_date,
                day_index=day_index,
                theme=theme,
            )
            await self._versions.complete_write(
                model=locked_trip,
                created_by=owner_id,
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DayAlreadyExistsError from exc
        return day

    async def create_stop(
        self,
        *,
        owner_id: UUID,
        day_id: UUID,
        expected_version: int,
        place_id: str,
        place_name: str | None,
        start_at: datetime,
        duration_minutes: int,
        estimated_cost_minor: int,
        location: GeoPoint | None,
        source: SourceMetadata | None,
    ) -> ItineraryStop:
        day = await self._require_day(owner_id=owner_id, day_id=day_id)
        locked_trip = await self._lock_trip(
            owner_id=owner_id,
            trip_id=day.trip_id,
            expected_version=expected_version,
        )
        if start_at.date() != day.date:
            raise InvalidItineraryError("stop start_at must fall on the trip day")

        stop = await self._itinerary.create_stop(
            day_id=day.id,
            place_id=place_id,
            place_name=place_name,
            start_at=start_at,
            duration_minutes=duration_minutes,
            estimated_cost_minor=estimated_cost_minor,
            location=location,
            source=source
            or SourceMetadata(
                provider="manual",
                provider_place_id=place_id,
                source_url=None,
                queried_at=datetime.now(UTC),
                freshness="unknown",
                confidence=1.0,
            ),
        )
        await self._itinerary.set_leg_modes(
            day_id=day.id,
            modes=self._normalize_leg_modes(
                day.leg_modes,
                count=max(len(day.stops), 0),
            ),
        )
        await self._versions.complete_write(model=locked_trip, created_by=owner_id)
        await self._session.commit()
        return stop

    async def update_stop(
        self,
        *,
        owner_id: UUID,
        stop_id: UUID,
        expected_version: int,
        place_id: str | None,
        place_name: str | None,
        set_place_name: bool,
        start_at: datetime | None,
        duration_minutes: int | None,
        estimated_cost_minor: int | None,
        location: GeoPoint | None,
        set_location: bool,
        source: SourceMetadata | None,
        set_source: bool,
    ) -> ItineraryStop:
        stop = await self._require_stop(owner_id=owner_id, stop_id=stop_id)
        day = await self._require_day(owner_id=owner_id, day_id=stop.day_id)
        locked_trip = await self._lock_trip(
            owner_id=owner_id,
            trip_id=day.trip_id,
            expected_version=expected_version,
        )
        if start_at is not None:
            if start_at.date() != day.date:
                raise InvalidItineraryError("stop start_at must fall on the trip day")

        updated = await self._itinerary.update_stop(
            stop_id=stop.id,
            place_id=place_id,
            place_name=place_name,
            set_place_name=set_place_name,
            start_at=start_at,
            duration_minutes=duration_minutes,
            estimated_cost_minor=estimated_cost_minor,
            location=location,
            set_location=set_location,
            source=source,
            set_source=set_source,
        )
        if updated is None:
            raise ItineraryNotFoundError
        await self._versions.complete_write(model=locked_trip, created_by=owner_id)
        await self._session.commit()
        return updated

    async def delete_stop(
        self,
        *,
        owner_id: UUID,
        stop_id: UUID,
        expected_version: int,
    ) -> None:
        stop = await self._require_stop(owner_id=owner_id, stop_id=stop_id)
        day = await self._require_day(owner_id=owner_id, day_id=stop.day_id)
        locked_trip = await self._lock_trip(
            owner_id=owner_id,
            trip_id=day.trip_id,
            expected_version=expected_version,
        )
        deleted = await self._itinerary.delete_stop(stop_id=stop.id)
        if not deleted:
            raise ItineraryNotFoundError
        modes = list(day.leg_modes)
        if modes:
            remove_index = min(
                max(stop.order_index - 1, 0),
                len(modes) - 1,
            )
            modes.pop(remove_index)
        await self._itinerary.set_leg_modes(
            day_id=day.id,
            modes=self._normalize_leg_modes(
                modes,
                count=max(len(day.stops) - 2, 0),
            ),
        )
        await self._versions.complete_write(model=locked_trip, created_by=owner_id)
        await self._session.commit()

    async def reorder_stops(
        self,
        *,
        owner_id: UUID,
        day_id: UUID,
        expected_version: int,
        stop_ids: list[UUID],
    ) -> TripDay:
        day = await self._require_day(owner_id=owner_id, day_id=day_id)
        locked_trip = await self._lock_trip(
            owner_id=owner_id,
            trip_id=day.trip_id,
            expected_version=expected_version,
        )
        current_ids = [stop.id for stop in day.stops]
        if (
            len(stop_ids) != len(current_ids)
            or len(set(stop_ids)) != len(stop_ids)
            or set(stop_ids) != set(current_ids)
        ):
            raise InvalidItineraryError("stop_ids must contain every stop exactly once")

        await self._itinerary.reorder_stops(day_id=day.id, stop_ids=stop_ids)
        await self._itinerary.set_leg_modes(
            day_id=day.id,
            modes=["walking"] * max(len(stop_ids) - 1, 0),
        )
        await self._versions.complete_write(model=locked_trip, created_by=owner_id)
        await self._session.commit()
        return await self._require_day(owner_id=owner_id, day_id=day.id)

    async def _require_trip(self, *, owner_id: UUID, trip_id: UUID) -> Trip:
        trip = await self._itinerary.get_trip_for_owner(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise ItineraryNotFoundError
        return trip

    async def _require_day(self, *, owner_id: UUID, day_id: UUID) -> TripDay:
        day = await self._itinerary.get_day_for_owner(owner_id=owner_id, day_id=day_id)
        if day is None:
            raise ItineraryNotFoundError
        return day

    async def _require_stop(self, *, owner_id: UUID, stop_id: UUID) -> ItineraryStop:
        stop = await self._itinerary.get_stop_for_owner(owner_id=owner_id, stop_id=stop_id)
        if stop is None:
            raise ItineraryNotFoundError
        return stop

    async def _lock_trip(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
    ) -> TripModel:
        try:
            return await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise ItineraryNotFoundError from exc

    @staticmethod
    def _normalize_leg_modes(modes: list[str], *, count: int) -> list[str]:
        normalized = [str(mode) for mode in modes[:count]]
        normalized.extend("walking" for _ in range(count - len(normalized)))
        return normalized
