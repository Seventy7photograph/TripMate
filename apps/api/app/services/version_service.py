# 文件说明：业务服务：version_service。
from dataclasses import dataclass
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense as ExpenseModel
from app.models.itinerary import ItineraryStop as ItineraryStopModel
from app.models.itinerary import TripDay as TripDayModel
from app.models.trip import Trip as TripModel
from app.models.trip_version import TripVersion


class VersionTripNotFoundError(Exception):
    pass


class VersionNotFoundError(Exception):
    pass


class VersionConflictError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("Trip version conflict")
        self.current_version = current_version


@dataclass(frozen=True, slots=True)
class TripVersionEntry:
    version: int
    snapshot: dict[str, object]
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TripVersionHistory:
    trip_id: UUID
    current_version: int
    versions: list[TripVersionEntry]


class VersionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_trip(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
    ) -> TripModel:
        # 行级锁让同一旅行的并发写入串行执行。
        result = await self._session.execute(
            select(TripModel)
            .where(
                TripModel.id == trip_id,
                TripModel.owner_id == owner_id,
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise VersionTripNotFoundError
        if model.version != expected_version:
            # 调用方必须重新读取最新版本后再重试。
            raise VersionConflictError(model.version)
        await self._ensure_current_snapshot(model, owner_id)
        return model

    async def record_initial_version(self, *, trip_id: UUID, created_by: UUID) -> None:
        model = await self._session.get(TripModel, trip_id)
        if model is None:
            raise VersionTripNotFoundError
        await self._record_snapshot(model, created_by)
        await self._session.flush()

    async def complete_write(self, *, model: TripModel, created_by: UUID) -> None:
        # 每次成功写入都推进版本号并记录快照。
        model.version += 1
        await self._session.flush()
        await self._session.refresh(model)
        await self._record_snapshot(model, created_by)
        await self._session.flush()

    async def list_versions(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
    ) -> TripVersionHistory:
        trip = await self._owned_trip(owner_id=owner_id, trip_id=trip_id)
        added_snapshot = await self._ensure_current_snapshot(trip, owner_id)
        if added_snapshot:
            await self._session.flush()
            await self._session.commit()
        result = await self._session.execute(
            select(TripVersion)
            .where(TripVersion.trip_id == trip_id)
            .order_by(TripVersion.version)
        )
        versions = [
            TripVersionEntry(
                version=item.version,
                snapshot=item.snapshot,
                created_by=item.created_by,
                created_at=item.created_at,
            )
            for item in result.scalars()
        ]
        return TripVersionHistory(
            trip_id=trip.id,
            current_version=trip.version,
            versions=versions,
        )

    async def restore(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        version: int,
        expected_version: int,
        created_by: UUID,
    ) -> TripModel:
        # 恢复旧版本本质上是一次新的向前写入，不能改写历史快照。
        trip = await self.lock_trip(
            owner_id=owner_id,
            trip_id=trip_id,
            expected_version=expected_version,
        )
        version_result = await self._session.execute(
            select(TripVersion).where(
                TripVersion.trip_id == trip_id,
                TripVersion.version == version,
            )
        )
        source = version_result.scalar_one_or_none()
        if source is None:
            raise VersionNotFoundError

        snapshot = source.snapshot
        trip_snapshot = cast(dict[str, object], snapshot["trip"])
        trip.brief = cast(dict[str, object], trip_snapshot["brief"])
        trip.status = str(trip_snapshot["status"])
        await self._replace_itinerary_from_snapshot(
            trip_id=trip.id,
            days=cast(list[dict[str, object]], snapshot.get("days", [])),
        )
        await self._replace_expenses_from_snapshot(
            trip_id=trip.id,
            expenses=cast(list[dict[str, object]], snapshot.get("expenses", [])),
        )
        await self.complete_write(model=trip, created_by=created_by)
        await self._session.commit()
        return trip

    async def _record_snapshot(self, trip: TripModel, created_by: UUID) -> None:
        snapshot = await self._build_snapshot(trip)
        self._session.add(
            TripVersion(
                trip_id=trip.id,
                version=trip.version,
                snapshot=snapshot,
                created_by=created_by,
            )
        )

    async def _ensure_current_snapshot(
        self,
        trip: TripModel,
        created_by: UUID,
    ) -> bool:
        result = await self._session.execute(
            select(TripVersion.id).where(
                TripVersion.trip_id == trip.id,
                TripVersion.version == trip.version,
            )
        )
        if result.scalar_one_or_none() is not None:
            return False
        await self._record_snapshot(trip, created_by)
        return True

    async def _build_snapshot(self, trip: TripModel) -> dict[str, object]:
        day_result = await self._session.execute(
            select(TripDayModel)
            .where(TripDayModel.trip_id == trip.id)
            .order_by(TripDayModel.date)
        )
        days = list(day_result.scalars())
        stops_by_day: dict[UUID, list[ItineraryStopModel]] = {}
        if days:
            stop_result = await self._session.execute(
                select(ItineraryStopModel)
                .where(ItineraryStopModel.day_id.in_([day.id for day in days]))
                .order_by(ItineraryStopModel.day_id, ItineraryStopModel.order_index)
            )
            for stop in stop_result.scalars():
                stops_by_day.setdefault(stop.day_id, []).append(stop)
        expense_result = await self._session.execute(
            select(ExpenseModel)
            .where(ExpenseModel.trip_id == trip.id)
            .order_by(ExpenseModel.expense_date, ExpenseModel.created_at)
        )
        expenses = list(expense_result.scalars())

        return {
            "trip": {
                "id": str(trip.id),
                "owner_id": str(trip.owner_id),
                "status": trip.status,
                "version": trip.version,
                "brief": trip.brief,
                "created_at": trip.created_at.isoformat(),
                "updated_at": trip.updated_at.isoformat(),
            },
            "days": [
                {
                    "id": str(day.id),
                    "date": day.date.isoformat(),
                    "day_index": day.day_index,
                    "theme": day.theme,
                    "created_at": day.created_at.isoformat(),
                    "updated_at": day.updated_at.isoformat(),
                    "stops": [
                        self._snapshot_stop(stop)
                        for stop in stops_by_day.get(day.id, [])
                    ],
                }
                for day in days
            ],
            "expenses": [
                {
                    "id": str(expense.id),
                    "payer_id": str(expense.payer_id),
                    "category": expense.category,
                    "amount_minor": expense.amount_minor,
                    "currency": expense.currency,
                    "expense_date": expense.expense_date.isoformat(),
                    "note": expense.note,
                    "created_at": expense.created_at.isoformat(),
                }
                for expense in expenses
            ],
        }

    @staticmethod
    def _snapshot_stop(stop: ItineraryStopModel) -> dict[str, object]:
        return {
            "id": str(stop.id),
            "place_id": stop.place_id,
            "place_name": stop.place_name,
            "start_at": stop.start_at.isoformat(),
            "duration_minutes": stop.duration_minutes,
            "order_index": stop.order_index,
            "estimated_cost_minor": stop.estimated_cost_minor,
            "location": (
                {
                    "longitude": stop.longitude,
                    "latitude": stop.latitude,
                    "coordinate_system": stop.coordinate_system,
                }
                if stop.longitude is not None
                and stop.latitude is not None
                and stop.coordinate_system is not None
                else None
            ),
            "source": stop.source,
            "created_at": stop.created_at.isoformat(),
            "updated_at": stop.updated_at.isoformat(),
        }

    async def _replace_itinerary_from_snapshot(
        self,
        *,
        trip_id: UUID,
        days: list[dict[str, object]],
    ) -> None:
        existing_result = await self._session.execute(
            select(TripDayModel.id).where(TripDayModel.trip_id == trip_id)
        )
        existing_ids = list(existing_result.scalars())
        if existing_ids:
            await self._session.execute(
                delete(ItineraryStopModel).where(
                    ItineraryStopModel.day_id.in_(existing_ids)
                )
            )
        await self._session.execute(
            delete(TripDayModel).where(TripDayModel.trip_id == trip_id)
        )
        await self._session.flush()

        for day in days:
            day_model = TripDayModel(
                id=UUID(str(day["id"])),
                trip_id=trip_id,
                date=date.fromisoformat(str(day["date"])),
                day_index=int(cast(int | str, day["day_index"])),
                theme=str(day["theme"]) if day.get("theme") is not None else None,
            )
            self._session.add(day_model)
            await self._session.flush()
            for stop in cast(list[dict[str, object]], day.get("stops", [])):
                location = stop.get("location")
                self._session.add(
                    ItineraryStopModel(
                        id=UUID(str(stop["id"])),
                        day_id=day_model.id,
                        place_id=str(stop["place_id"]),
                        place_name=(
                            str(stop["place_name"])
                            if stop.get("place_name") is not None
                            else None
                        ),
                        start_at=datetime.fromisoformat(str(stop["start_at"])),
                        duration_minutes=int(
                            cast(int | str, stop["duration_minutes"])
                        ),
                        order_index=int(cast(int | str, stop["order_index"])),
                        estimated_cost_minor=int(
                            cast(int | str, stop["estimated_cost_minor"])
                        ),
                        longitude=(
                            float(cast(float | int | str, location["longitude"]))
                            if isinstance(location, dict)
                            and location.get("longitude") is not None
                            else None
                        ),
                        latitude=(
                            float(cast(float | int | str, location["latitude"]))
                            if isinstance(location, dict)
                            and location.get("latitude") is not None
                            else None
                        ),
                        coordinate_system=(
                            str(location["coordinate_system"])
                            if isinstance(location, dict)
                            and location.get("coordinate_system") is not None
                            else None
                        ),
                        source=cast(dict[str, object], stop["source"]),
                    )
                )
            await self._session.flush()

    async def _replace_expenses_from_snapshot(
        self,
        *,
        trip_id: UUID,
        expenses: list[dict[str, object]],
    ) -> None:
        await self._session.execute(
            delete(ExpenseModel).where(ExpenseModel.trip_id == trip_id)
        )
        await self._session.flush()
        for expense in expenses:
            self._session.add(
                ExpenseModel(
                    id=UUID(str(expense["id"])),
                    trip_id=trip_id,
                    payer_id=UUID(str(expense["payer_id"])),
                    category=str(expense["category"]),
                    amount_minor=int(cast(int | str, expense["amount_minor"])),
                    currency=str(expense["currency"]),
                    expense_date=date.fromisoformat(str(expense["expense_date"])),
                    note=(
                        str(expense["note"])
                        if expense.get("note") is not None
                        else None
                    ),
                    created_at=(
                        datetime.fromisoformat(str(expense["created_at"]))
                        if expense.get("created_at") is not None
                        else datetime.now().astimezone()
                    ),
                )
            )
        await self._session.flush()

    async def _owned_trip(self, *, owner_id: UUID, trip_id: UUID) -> TripModel:
        result = await self._session.execute(
            select(TripModel).where(
                TripModel.id == trip_id,
                TripModel.owner_id == owner_id,
            )
        )
        trip = result.scalar_one_or_none()
        if trip is None:
            raise VersionTripNotFoundError
        return trip
