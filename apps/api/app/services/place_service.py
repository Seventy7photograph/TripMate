# 文件说明：业务服务：place_service。
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.providers.amap import AmapMapProvider
from app.providers.base import (
    GeoPoint,
    MapProvider,
    PlaceQuery,
    PlaceResult,
    ProviderConfigurationError,
    RouteRequest,
    RouteResult,
    normalize_category_text,
)
from app.providers.mock_map import MockMapProvider
from app.repositories.place_repository import PlaceRepository


class PlaceNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PlaceSearchOutcome:
    provider: str
    profile: str
    cached: bool
    results: list[PlaceResult]


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    profile: str
    provider: str
    configured: bool
    capabilities: list[str]


def create_map_provider(settings: Settings) -> MapProvider:
    if settings.effective_map_provider_profile == "mock":
        return MockMapProvider()
    if settings.amap_web_service_key is None:
        raise ProviderConfigurationError("AMAP_WEB_SERVICE_KEY is required")
    return AmapMapProvider(
        key=settings.amap_web_service_key.get_secret_value(),
        base_url=settings.amap_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
        proxy_url=_proxy_url(settings),
    )


def _proxy_url(settings: Settings) -> str | None:
    return (
        settings.outbound_proxy_url.get_secret_value()
        if settings.outbound_proxy_url is not None
        else None
    )


class PlaceService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: MapProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider or create_map_provider(settings)
        self._places = PlaceRepository(session)

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def name(self) -> str:
        return self._provider.name

    async def status(self) -> ProviderStatus:
        configured = (
            self._provider.name == "mock"
            or self._settings.amap_web_service_key is not None
        )
        return ProviderStatus(
            profile=self._settings.effective_map_provider_profile,
            provider=self._provider.name,
            configured=configured,
            capabilities=["search", "nearby", "detail", "geocode", "route"],
        )

    async def search(self, query: PlaceQuery) -> PlaceSearchOutcome:
        query_hash = self._query_hash(query)
        if self._provider.name != "mock":
            cache = await self._places.get_search_cache(
                provider=self._provider.name,
                query_hash=query_hash,
            )
            if cache is not None:
                cached_results = [
                    replace(
                        place,
                        category=normalize_category_text(place.category),
                        source=replace(place.source, freshness="cached"),
                    )
                    for place in PlaceRepository.cached_results(cache)
                ]
                return PlaceSearchOutcome(
                    provider=self._provider.name,
                    profile=self._settings.effective_map_provider_profile,
                    cached=True,
                    results=cached_results,
                )

        results = await self._provider.search_places(query)
        stored_results = [await self._places.upsert_place(place) for place in results]
        if self._provider.name != "mock" and self._settings.place_cache_ttl_seconds > 0:
            fetched_at = datetime.now(UTC)
            await self._places.save_search_cache(
                provider=self._provider.name,
                query_hash=query_hash,
                query_text=self._query_text(query),
                results=stored_results,
                fetched_at=fetched_at,
                expires_at=fetched_at
                + timedelta(seconds=self._settings.place_cache_ttl_seconds),
            )
        await self._session.commit()
        return PlaceSearchOutcome(
            provider=self._provider.name,
            profile=self._settings.effective_map_provider_profile,
            cached=False,
            results=stored_results,
        )

    async def get(self, provider_place_id: str) -> PlaceResult:
        if self._provider.name != "mock":
            cached = await self._places.get_place(
                provider=self._provider.name,
                provider_place_id=provider_place_id,
            )
            if cached is not None and self._place_cache_valid(cached):
                return replace(
                    cached,
                    source=replace(cached.source, freshness="cached"),
                )
        try:
            result = await self._provider.get_place(provider_place_id)
        except KeyError as exc:
            raise PlaceNotFoundError from exc
        stored = await self._places.upsert_place(result)
        await self._session.commit()
        return stored

    async def geocode(self, address: str) -> GeoPoint:
        return await self._provider.geocode(address)

    async def route(self, request: RouteRequest) -> RouteResult:
        return await self._provider.get_route(request)

    def _place_cache_valid(self, place: PlaceResult) -> bool:
        if self._settings.place_cache_ttl_seconds <= 0:
            return False
        return (
            datetime.now(UTC) - place.source.queried_at
        ).total_seconds() < self._settings.place_cache_ttl_seconds

    @staticmethod
    def _query_text(query: PlaceQuery) -> str:
        return json.dumps(
            {
                "keyword": query.keyword,
                "city": query.city,
                "types": query.types,
                "limit": query.limit,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _query_hash(self, query: PlaceQuery) -> str:
        return hashlib.sha256(
            f"{self._provider.name}:{self._query_text(query)}".encode()
        ).hexdigest()
