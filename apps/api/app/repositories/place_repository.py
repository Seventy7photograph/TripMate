# 文件说明：数据访问仓储：place_repository。
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.place import Place as PlaceModel
from app.models.place import PlaceSearchCache
from app.providers.base import PlaceResult, place_from_record


class PlaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_place(self, *, provider: str, provider_place_id: str) -> PlaceResult | None:
        result = await self._session.execute(
            select(PlaceModel).where(
                PlaceModel.provider == provider,
                PlaceModel.provider_place_id == provider_place_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def upsert_place(self, place: PlaceResult) -> PlaceResult:
        result = await self._session.execute(
            select(PlaceModel).where(
                PlaceModel.provider == place.source.provider,
                PlaceModel.provider_place_id == place.provider_place_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = PlaceModel(
                provider=place.source.provider,
                provider_place_id=place.provider_place_id,
                name=place.name,
                fetched_at=place.source.queried_at,
                source=place.source.to_record(),
            )
            self._session.add(model)

        model.name = place.name
        model.category = place.category
        model.address = place.address
        model.longitude = (
            Decimal(str(place.location.longitude))
            if place.location is not None
            else None
        )
        model.latitude = (
            Decimal(str(place.location.latitude))
            if place.location is not None
            else None
        )
        model.coordinate_system = (
            place.location.coordinate_system if place.location is not None else None
        )
        model.tel = place.tel
        model.opening_hours = place.opening_hours
        model.reference_price = place.reference_price
        model.source = place.source.to_record()
        model.fetched_at = place.source.queried_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def get_search_cache(
        self,
        *,
        provider: str,
        query_hash: str,
    ) -> PlaceSearchCache | None:
        result = await self._session.execute(
            select(PlaceSearchCache).where(
                PlaceSearchCache.provider == provider,
                PlaceSearchCache.query_hash == query_hash,
                PlaceSearchCache.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

    async def save_search_cache(
        self,
        *,
        provider: str,
        query_hash: str,
        query_text: str,
        results: list[PlaceResult],
        fetched_at: datetime,
        expires_at: datetime,
    ) -> None:
        result = await self._session.execute(
            select(PlaceSearchCache).where(
                PlaceSearchCache.provider == provider,
                PlaceSearchCache.query_hash == query_hash,
            )
        )
        model = result.scalar_one_or_none()
        records: list[dict[str, object]] = [
            {
                "provider_place_id": place.provider_place_id,
                "name": place.name,
                "category": place.category,
                "address": place.address,
                "location": (
                    {
                        "longitude": place.location.longitude,
                        "latitude": place.location.latitude,
                        "coordinate_system": place.location.coordinate_system,
                    }
                    if place.location is not None
                    else None
                ),
                "tel": place.tel,
                "opening_hours": place.opening_hours,
                "source": place.source.to_record(),
                "reference_price": place.reference_price,
            }
            for place in results
        ]
        if model is None:
            model = PlaceSearchCache(
                provider=provider,
                query_hash=query_hash,
                query_text=query_text,
                results=records,
                fetched_at=fetched_at,
                expires_at=expires_at,
            )
            self._session.add(model)
        else:
            model.query_text = query_text
            model.results = records
            model.fetched_at = fetched_at
            model.expires_at = expires_at
        await self._session.flush()

    @staticmethod
    def cached_results(cache: PlaceSearchCache) -> list[PlaceResult]:
        return [place_from_record(record) for record in cache.results]

    @staticmethod
    def _to_domain(model: PlaceModel) -> PlaceResult:
        from app.domain.itinerary import SourceMetadata
        from app.providers.base import GeoPoint

        location = None
        if model.longitude is not None and model.latitude is not None:
            location = GeoPoint(
                longitude=float(model.longitude),
                latitude=float(model.latitude),
                coordinate_system=model.coordinate_system or "GCJ-02",  # type: ignore[arg-type]
            )
        return PlaceResult(
            provider_place_id=model.provider_place_id,
            name=model.name,
            category=model.category,
            address=model.address,
            location=location,
            tel=model.tel,
            opening_hours=list(model.opening_hours),
            source=SourceMetadata.from_record(model.source),
            reference_price=model.reference_price,
        )
