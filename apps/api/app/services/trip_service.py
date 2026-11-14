# 文件说明：业务服务：trip_service。
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trip import Trip, TripBrief, TripStatus
from app.repositories.trip_repository import TripRepository
from app.services.version_service import VersionService, VersionTripNotFoundError


class TripNotFoundError(Exception):
    pass


class TripService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._trips = TripRepository(session)
        self._versions = VersionService(session)

    async def create(self, *, owner_id: UUID, brief: TripBrief) -> Trip:
        trip = await self._trips.create(owner_id=owner_id, brief=brief)
        await self._versions.record_initial_version(
            trip_id=trip.id,
            created_by=owner_id,
        )
        await self._session.commit()
        return trip

    async def list(
        self,
        *,
        owner_id: UUID,
        include_archived: bool,
    ) -> list[Trip]:
        return await self._trips.list_for_owner(
            owner_id,
            include_archived=include_archived,
        )

    async def get(self, *, owner_id: UUID, trip_id: UUID) -> Trip:
        trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise TripNotFoundError
        return trip

    async def update(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
        brief: TripBrief | None,
        status: TripStatus | None,
    ) -> Trip:
        try:
            locked = await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise TripNotFoundError from exc
        trip = await self._trips.update(
            owner_id=owner_id,
            trip_id=trip_id,
            brief=brief,
            status=status,
        )
        if trip is None:
            raise TripNotFoundError
        await self._versions.complete_write(model=locked, created_by=owner_id)
        await self._session.commit()
        return await self.get(owner_id=owner_id, trip_id=trip_id)

    async def archive(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        expected_version: int,
    ) -> None:
        try:
            locked = await self._versions.lock_trip(
                owner_id=owner_id,
                trip_id=trip_id,
                expected_version=expected_version,
            )
        except VersionTripNotFoundError as exc:
            raise TripNotFoundError from exc
        trip = await self._trips.archive(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise TripNotFoundError
        await self._versions.complete_write(model=locked, created_by=owner_id)
        await self._session.commit()
