# 文件说明：数据访问仓储：itinerary_repository。
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.itinerary import ItineraryStop, SourceMetadata, TripDay
from app.domain.location import GeoPoint
from app.domain.trip import Trip
from app.models.itinerary import ItineraryStop as ItineraryStopModel
from app.models.itinerary import TripDay as TripDayModel
from app.models.trip import Trip as TripModel
from app.repositories.trip_repository import TripRepository


class ItineraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._trips = TripRepository(session)

    async def get_trip_for_owner(self, *, owner_id: UUID, trip_id: UUID) -> Trip | None:
        return await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)

    async def list_days(self, *, trip_id: UUID) -> list[TripDay]:
        day_result = await self._session.execute(
            select(TripDayModel)
            .where(TripDayModel.trip_id == trip_id)
            .order_by(TripDayModel.date)
        )
        days = list(day_result.scalars())
        if not days:
            return []

        stop_result = await self._session.execute(
            select(ItineraryStopModel)
            .where(ItineraryStopModel.day_id.in_([day.id for day in days]))
            .order_by(ItineraryStopModel.order_index)
        )
        stops_by_day: dict[UUID, list[ItineraryStop]] = defaultdict(list)
        for stop in stop_result.scalars():
            stops_by_day[stop.day_id].append(self._stop_to_domain(stop))

        return [
            self._day_to_domain(day, stops_by_day.get(day.id, []))
            for day in days
        ]

    async def get_day_for_owner(self, *, owner_id: UUID, day_id: UUID) -> TripDay | None:
        model = await self._get_day_model(owner_id=owner_id, day_id=day_id)
        if model is None:
            return None
        stops = await self._list_stop_models(model.id)
        return self._day_to_domain(model, [self._stop_to_domain(stop) for stop in stops])

    async def get_stop_for_owner(
        self,
        *,
        owner_id: UUID,
        stop_id: UUID,
    ) -> ItineraryStop | None:
        model = await self._get_stop_model(owner_id=owner_id, stop_id=stop_id)
        return self._stop_to_domain(model) if model is not None else None

    async def has_day(self, *, trip_id: UUID, day_date: date) -> bool:
        result = await self._session.execute(
            select(TripDayModel.id).where(
                TripDayModel.trip_id == trip_id,
                TripDayModel.date == day_date,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_day(
        self,
        *,
        trip_id: UUID,
        day_date: date,
        day_index: int,
        theme: str | None,
    ) -> TripDay:
        model = TripDayModel(
            trip_id=trip_id,
            date=day_date,
            day_index=day_index,
            theme=theme,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._day_to_domain(model, [])

    async def create_stop(
        self,
        *,
        day_id: UUID,
        place_id: str,
        place_name: str | None,
        start_at: datetime,
        duration_minutes: int,
        estimated_cost_minor: int,
        location: GeoPoint | None,
        source: SourceMetadata,
    ) -> ItineraryStop:
        result = await self._session.execute(
            select(func.max(ItineraryStopModel.order_index)).where(
                ItineraryStopModel.day_id == day_id
            )
        )
        current_max = result.scalar_one()
        model = ItineraryStopModel(
            day_id=day_id,
            place_id=place_id,
            place_name=place_name,
            start_at=start_at,
            duration_minutes=duration_minutes,
            order_index=(current_max + 1) if current_max is not None else 0,
            estimated_cost_minor=estimated_cost_minor,
            longitude=location.longitude if location is not None else None,
            latitude=location.latitude if location is not None else None,
            coordinate_system=(
                location.coordinate_system if location is not None else None
            ),
            source=source.to_record(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._stop_to_domain(model)

    async def update_stop(
        self,
        *,
        stop_id: UUID,
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
    ) -> ItineraryStop | None:
        model = await self._session.get(ItineraryStopModel, stop_id)
        if model is None:
            return None

        if place_id is not None:
            model.place_id = place_id
        if set_place_name:
            model.place_name = place_name
        if start_at is not None:
            model.start_at = start_at
        if duration_minutes is not None:
            model.duration_minutes = duration_minutes
        if estimated_cost_minor is not None:
            model.estimated_cost_minor = estimated_cost_minor
        if set_location:
            model.longitude = location.longitude if location is not None else None
            model.latitude = location.latitude if location is not None else None
            model.coordinate_system = (
                location.coordinate_system if location is not None else None
            )
        if set_source:
            model.source = (source or SourceMetadata(
                provider="manual",
                provider_place_id=model.place_id,
                source_url=None,
                queried_at=datetime.now(UTC),
                freshness="unknown",
                confidence=1.0,
            )).to_record()

        await self._session.flush()
        await self._session.refresh(model)
        return self._stop_to_domain(model)

    async def delete_stop(self, *, stop_id: UUID) -> bool:
        model = await self._session.get(ItineraryStopModel, stop_id)
        if model is None:
            return False
        day_id = model.day_id
        await self._session.delete(model)
        await self._session.flush()
        await self._reindex_stops(day_id)
        return True

    async def reorder_stops(self, *, day_id: UUID, stop_ids: list[UUID]) -> None:
        stops = await self._list_stop_models(day_id)
        by_id = {stop.id: stop for stop in stops}
        offset = len(stops) + 1
        for index, stop_id in enumerate(stop_ids):
            by_id[stop_id].order_index = offset + index
        await self._session.flush()
        for index, stop_id in enumerate(stop_ids):
            by_id[stop_id].order_index = index
        await self._session.flush()

    async def set_leg_modes(self, *, day_id: UUID, modes: list[str]) -> None:
        model = await self._session.get(TripDayModel, day_id)
        if model is None:
            return
        model.leg_modes = modes
        await self._session.flush()

    async def _reindex_stops(self, day_id: UUID) -> None:
        stops = await self._list_stop_models(day_id)
        offset = len(stops) + 1
        for index, stop in enumerate(stops):
            stop.order_index = offset + index
        await self._session.flush()
        for index, stop in enumerate(stops):
            stop.order_index = index
        await self._session.flush()

    async def _list_stop_models(self, day_id: UUID) -> list[ItineraryStopModel]:
        result = await self._session.execute(
            select(ItineraryStopModel)
            .where(ItineraryStopModel.day_id == day_id)
            .order_by(ItineraryStopModel.order_index)
        )
        return list(result.scalars())

    async def _get_day_model(self, *, owner_id: UUID, day_id: UUID) -> TripDayModel | None:
        result = await self._session.execute(
            select(TripDayModel)
            .join(TripModel, TripDayModel.trip_id == TripModel.id)
            .where(
                TripDayModel.id == day_id,
                TripModel.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_stop_model(
        self,
        *,
        owner_id: UUID,
        stop_id: UUID,
    ) -> ItineraryStopModel | None:
        result = await self._session.execute(
            select(ItineraryStopModel)
            .join(TripDayModel, ItineraryStopModel.day_id == TripDayModel.id)
            .join(TripModel, TripDayModel.trip_id == TripModel.id)
            .where(
                ItineraryStopModel.id == stop_id,
                TripModel.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _day_to_domain(model: TripDayModel, stops: list[ItineraryStop]) -> TripDay:
        return TripDay(
            id=model.id,
            trip_id=model.trip_id,
            date=model.date,
            day_index=model.day_index,
            theme=model.theme,
            leg_modes=list(model.leg_modes),
            stops=stops,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _stop_to_domain(model: ItineraryStopModel) -> ItineraryStop:
        return ItineraryStop(
            id=model.id,
            day_id=model.day_id,
            place_id=model.place_id,
            place_name=model.place_name,
            start_at=model.start_at,
            duration_minutes=model.duration_minutes,
            order_index=model.order_index,
            estimated_cost_minor=model.estimated_cost_minor,
            location=(
                GeoPoint(
                    longitude=model.longitude,
                    latitude=model.latitude,
                    coordinate_system=cast(
                        Literal["GCJ-02", "WGS84"],
                        model.coordinate_system,
                    ),
                )
                if model.longitude is not None
                and model.latitude is not None
                and model.coordinate_system is not None
                else None
            ),
            source=SourceMetadata.from_record(model.source),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
