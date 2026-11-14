# 文件说明：业务服务：favorite_service。
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite import Favorite as FavoriteModel
from app.repositories.trip_repository import TripRepository
from app.schemas.share import FavoriteCreateRequest, FavoriteUpdateRequest

DEFAULT_FAVORITE_FOLDERS = {
    "place": "地点收藏",
    "trip": "行程收藏",
}


class FavoriteNotFoundError(Exception):
    pass


class FavoriteTargetNotFoundError(Exception):
    pass


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._trips = TripRepository(session)

    async def create(
        self,
        *,
        owner_id: UUID,
        payload: FavoriteCreateRequest,
    ) -> tuple[FavoriteModel, bool]:
        if payload.kind == "trip":
            try:
                trip_id = UUID(payload.target_id)
            except ValueError as exc:
                raise FavoriteTargetNotFoundError from exc
            trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
            if trip is None:
                raise FavoriteTargetNotFoundError
        existing = await self._session.scalar(
            select(FavoriteModel).where(
                FavoriteModel.owner_id == owner_id,
                FavoriteModel.kind == payload.kind,
                FavoriteModel.target_id == payload.target_id,
            )
        )
        if existing is not None:
            return existing, False
        model = FavoriteModel(
            owner_id=owner_id,
            kind=payload.kind,
            target_id=payload.target_id,
            label=payload.label,
            folder=payload.folder or DEFAULT_FAVORITE_FOLDERS[payload.kind],
            note=payload.note,
            details=payload.details,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return model, True

    async def list(
        self,
        *,
        owner_id: UUID,
        kind: str | None,
        folder: str | None,
    ) -> list[FavoriteModel]:
        statement = select(FavoriteModel).where(FavoriteModel.owner_id == owner_id)
        if kind is not None:
            statement = statement.where(FavoriteModel.kind == kind)
        if folder is not None:
            statement = statement.where(FavoriteModel.folder == folder)
        result = await self._session.execute(
            statement.order_by(FavoriteModel.created_at.desc())
        )
        return list(result.scalars())

    async def update(
        self,
        *,
        owner_id: UUID,
        favorite_id: UUID,
        payload: FavoriteUpdateRequest,
    ) -> FavoriteModel:
        result = await self._session.execute(
            select(FavoriteModel).where(
                FavoriteModel.id == favorite_id,
                FavoriteModel.owner_id == owner_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise FavoriteNotFoundError
        if payload.folder is not None:
            model.folder = payload.folder
        if "note" in payload.model_fields_set:
            model.note = payload.note
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return model

    async def remove(self, *, owner_id: UUID, favorite_id: UUID) -> None:
        result = await self._session.execute(
            select(FavoriteModel).where(
                FavoriteModel.id == favorite_id,
                FavoriteModel.owner_id == owner_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise FavoriteNotFoundError
        await self._session.delete(model)
        await self._session.commit()
