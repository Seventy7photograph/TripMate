# 文件说明：数据访问仓储：trip_repository。
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trip import Trip, TripBrief, TripStatus
from app.models.trip import Trip as TripModel


class TripRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, owner_id: UUID, brief: TripBrief) -> Trip:
        model = TripModel(
            owner_id=owner_id,
            status="draft",
            version=1,
            brief=brief.to_record(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        include_archived: bool,
    ) -> list[Trip]:
        statement = (
            select(TripModel)
            .where(TripModel.owner_id == owner_id)
            .order_by(TripModel.created_at.desc())
        )
        if not include_archived:
            statement = statement.where(TripModel.status != "archived")
        result = await self._session.execute(statement)
        return [self._to_domain(model) for model in result.scalars()]

    async def get_for_owner(self, *, owner_id: UUID, trip_id: UUID) -> Trip | None:
        model = await self._get_model(owner_id=owner_id, trip_id=trip_id)
        return self._to_domain(model) if model is not None else None

    async def update(
        self,
        *,
        owner_id: UUID,
        trip_id: UUID,
        brief: TripBrief | None,
        status: TripStatus | None,
    ) -> Trip | None:
        model = await self._get_model(owner_id=owner_id, trip_id=trip_id)
        if model is None:
            return None

        if brief is not None:
            model.brief = brief.to_record()
        if status is not None:
            model.status = status

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def archive(self, *, owner_id: UUID, trip_id: UUID) -> Trip | None:
        model = await self._get_model(owner_id=owner_id, trip_id=trip_id)
        if model is None:
            return None
        if model.status == "archived":
            return self._to_domain(model)

        model.status = "archived"
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def _get_model(self, *, owner_id: UUID, trip_id: UUID) -> TripModel | None:
        result = await self._session.execute(
            select(TripModel).where(
                TripModel.id == trip_id,
                TripModel.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(model: TripModel) -> Trip:
        return Trip(
            id=model.id,
            owner_id=model.owner_id,
            status=cast(TripStatus, model.status),
            version=model.version,
            brief=TripBrief.from_record(model.brief),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
