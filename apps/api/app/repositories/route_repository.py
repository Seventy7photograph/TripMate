# 文件说明：数据访问仓储：route_repository。
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.itinerary import SourceMetadata
from app.domain.route import RouteLeg
from app.models.route_leg import RouteLeg as RouteLegModel
from app.providers.base import RouteMode, RouteResult


class RouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_cached(
        self,
        *,
        day_id: UUID,
        from_stop_id: UUID,
        to_stop_id: UUID,
        mode: RouteMode,
        ttl_seconds: int,
    ) -> RouteLeg | None:
        if ttl_seconds <= 0:
            return None
        result = await self._session.execute(
            select(RouteLegModel).where(
                RouteLegModel.day_id == day_id,
                RouteLegModel.from_stop_id == from_stop_id,
                RouteLegModel.to_stop_id == to_stop_id,
                RouteLegModel.mode == mode,
                RouteLegModel.fetched_at
                > datetime.now(UTC) - timedelta(seconds=ttl_seconds),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def upsert(
        self,
        *,
        day_id: UUID,
        from_stop_id: UUID,
        to_stop_id: UUID,
        mode: RouteMode,
        route: RouteResult,
    ) -> RouteLeg:
        result = await self._session.execute(
            select(RouteLegModel).where(
                RouteLegModel.day_id == day_id,
                RouteLegModel.from_stop_id == from_stop_id,
                RouteLegModel.to_stop_id == to_stop_id,
                RouteLegModel.mode == mode,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = RouteLegModel(
                day_id=day_id,
                from_stop_id=from_stop_id,
                to_stop_id=to_stop_id,
                mode=mode,
                distance_m=route.distance_m,
                duration_s=route.duration_s,
                polyline=route.polyline,
                source=route.source.to_record(),
                fetched_at=route.source.queried_at,
            )
            self._session.add(model)
        else:
            model.distance_m = route.distance_m
            model.duration_s = route.duration_s
            model.polyline = route.polyline
            model.source = route.source.to_record()
            model.fetched_at = route.source.queried_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: RouteLegModel) -> RouteLeg:
        return RouteLeg(
            id=model.id,
            day_id=model.day_id,
            from_stop_id=model.from_stop_id,
            to_stop_id=model.to_stop_id,
            mode=cast(RouteMode, model.mode),
            distance_m=model.distance_m,
            duration_s=model.duration_s,
            polyline=model.polyline,
            source=SourceMetadata.from_record(model.source),
        )
