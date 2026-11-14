# 文件说明：业务服务：patch_service。
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.itinerary import ItineraryStop
from app.models.itinerary_patch import ItineraryPatch as ItineraryPatchModel
from app.models.trip import Trip as TripModel
from app.repositories.itinerary_repository import ItineraryRepository
from app.schemas.itinerary import ItineraryResponse
from app.services.version_service import (
    VersionService,
    VersionTripNotFoundError,
)

_CHINESE_COUNTS = {
    "一": 1,
    "两": 2,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


class PatchNotFoundError(Exception):
    pass


class PatchStateError(Exception):
    pass


class PatchStaleError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("Patch was created from an older itinerary version")
        self.current_version = current_version


class UnsupportedReplanError(Exception):
    pass


class NoStopsToPatchError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PatchView:
    id: UUID
    trip_id: UUID
    target_day_id: UUID
    base_version: int
    applied_version: int | None
    status: str
    instruction: str
    changes: dict[str, object]
    created_at: datetime
    applied_at: datetime | None


@dataclass(frozen=True, slots=True)
class PatchApplyView:
    patch: PatchView
    itinerary: ItineraryResponse


class PatchService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._itineraries = ItineraryRepository(session)
        self._versions = VersionService(session)

    async def create_replan(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
        day_id: UUID,
        instruction: str,
    ) -> PatchView:
        # 先锁定旅行，确保评估 Patch 时 base_version 稳定。
        try:
            trip = await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise PatchNotFoundError from exc

        day = await self._itineraries.get_day_for_owner(
            owner_id=owner_id,
            day_id=day_id,
        )
        if day is None or day.trip_id != trip.id:
            raise PatchNotFoundError
        if not day.stops:
            raise NoStopsToPatchError

        removed = self._select_removed_stops(day.stops, instruction)
        removed_ids = {stop.id for stop in removed}
        after_stops = [stop for stop in day.stops if stop.id not in removed_ids]
        changes = {
            "target_day_date": day.date.isoformat(),
            "removed_stop_ids": [str(stop.id) for stop in removed],
            "added_stop_ids": [],
            "before_stops": [self._stop_diff(stop) for stop in day.stops],
            "after_stops": [self._stop_diff(stop) for stop in after_stops],
            "before_stop_count": len(day.stops),
            "after_stop_count": len(after_stops),
        }
        patch = ItineraryPatchModel(
            trip_id=trip.id,
            target_day_id=day.id,
            created_by=owner_id,
            base_version=trip.version,
            status="pending",
            instruction=instruction,
            changes=changes,
        )
        self._session.add(patch)
        await self._session.flush()
        await self._session.refresh(patch)
        await self._session.commit()
        return self._view(patch)

    async def get(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        patch_id: UUID,
    ) -> PatchView:
        patch = await self._get_owned_patch(
            owner_id=owner_id,
            trip_id=trip_id,
            patch_id=patch_id,
        )
        return self._view(patch)

    async def apply(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        patch_id: UUID,
        expected_version: int,
    ) -> PatchApplyView:
        try:
            trip = await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise PatchNotFoundError from exc

        patch = await self._get_owned_patch(
            owner_id=owner_id,
            trip_id=trip_id,
            patch_id=patch_id,
            for_update=True,
        )
        if patch.status != "pending":
            raise PatchStateError
        if patch.base_version != trip.version:
            # 不允许把 Patch 应用到不同版本的行程快照。
            raise PatchStaleError(trip.version)

        # 只执行已经确认并持久化的变更集。
        removed_ids = self._removed_stop_ids(patch)
        for stop_id in removed_ids:
            await self._itineraries.delete_stop(stop_id=stop_id)
        await self._versions.complete_write(model=trip, created_by=owner_id)

        patch.status = "applied"
        patch.applied_version = trip.version
        patch.applied_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(patch)
        days = await self._itineraries.list_days(trip_id=trip.id)
        await self._session.commit()
        itinerary = ItineraryResponse.model_validate(
            {
                "trip_id": trip.id,
                "version": trip.version,
                "days": days,
            }
        )
        return PatchApplyView(patch=self._view(patch), itinerary=itinerary)

    async def discard(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        patch_id: UUID,
        expected_version: int,
    ) -> PatchView:
        try:
            await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise PatchNotFoundError from exc
        patch = await self._get_owned_patch(
            owner_id=owner_id,
            trip_id=trip_id,
            patch_id=patch_id,
            for_update=True,
        )
        if patch.status != "pending":
            raise PatchStateError
        patch.status = "discarded"
        await self._session.flush()
        await self._session.refresh(patch)
        await self._session.commit()
        return self._view(patch)

    async def _get_owned_patch(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        patch_id: UUID,
        for_update: bool = False,
    ) -> ItineraryPatchModel:
        statement = (
            select(ItineraryPatchModel)
            .join(TripModel, ItineraryPatchModel.trip_id == TripModel.id)
            .where(
                ItineraryPatchModel.id == patch_id,
                ItineraryPatchModel.trip_id == trip_id,
                TripModel.owner_id == owner_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        patch = result.scalar_one_or_none()
        if patch is None:
            raise PatchNotFoundError
        return patch

    @staticmethod
    def _select_removed_stops(
        stops: list[ItineraryStop],
        instruction: str,
    ) -> list[ItineraryStop]:
        normalized = instruction.strip()
        count_match = re.search(
            r"(?:减少|删除|去掉|移除)\s*([一二两三四五六七八九十\d]+)\s*个",
            normalized,
        )
        if count_match:
            raw_count = count_match.group(1)
            count = (
                int(raw_count)
                if raw_count.isdigit()
                else _CHINESE_COUNTS.get(raw_count, 1)
            )
            return stops[-count:]
        if any(word in normalized for word in ("减少景点", "删除景点", "去掉景点")):
            return stops[-1:]

        name_match = re.search(
            r"(?:删除|去掉|移除)\s*[「“\"]?(.+?)[」”\"]?$",
            normalized,
        )
        if name_match:
            target = name_match.group(1).strip()
            matched = [
                stop
                for stop in stops
                if target and target in (stop.place_name or stop.place_id)
            ]
            if not matched:
                raise UnsupportedReplanError
            return matched
        raise UnsupportedReplanError

    @staticmethod
    def _removed_stop_ids(patch: ItineraryPatchModel) -> list[UUID]:
        raw_ids = patch.changes.get("removed_stop_ids", [])
        if not isinstance(raw_ids, list):
            raise PatchStateError
        return [UUID(str(value)) for value in raw_ids]

    @staticmethod
    def _stop_diff(stop: ItineraryStop) -> dict[str, object]:
        return {
            "id": str(stop.id),
            "place_id": stop.place_id,
            "place_name": stop.place_name,
            "start_at": stop.start_at.isoformat(),
            "duration_minutes": stop.duration_minutes,
            "order_index": stop.order_index,
        }

    @staticmethod
    def _view(patch: ItineraryPatchModel) -> PatchView:
        return PatchView(
            id=patch.id,
            trip_id=patch.trip_id,
            target_day_id=patch.target_day_id,
            base_version=patch.base_version,
            applied_version=patch.applied_version,
            status=patch.status,
            instruction=patch.instruction,
            changes=cast(dict[str, object], patch.changes),
            created_at=patch.created_at,
            applied_at=patch.applied_at,
        )
