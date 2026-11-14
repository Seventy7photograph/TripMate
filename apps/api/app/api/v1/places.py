# 文件说明：FastAPI 路由：places。
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_feature,
)
from app.providers.base import (
    PlaceQuery,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.place import (
    GeocodeResponse,
    PlaceResponse,
    PlaceSearchResponse,
    ProviderStatusResponse,
)
from app.services.place_service import (
    PlaceNotFoundError,
    PlaceService,
    create_map_provider,
)

router = APIRouter(tags=["places"])


async def get_place_service(
    session: SessionDep,
    settings: SettingsDep,
) -> AsyncIterator[PlaceService]:
    provider = create_map_provider(settings)
    service = PlaceService(session, settings, provider)
    try:
        yield service
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()


PlaceServiceDep = Annotated[PlaceService, Depends(get_place_service)]
MapFeatureDep = Annotated[None, Depends(require_feature("map_provider"))]


def provider_http_exception(exc: ProviderError) -> HTTPException:
    status_code = (
        status.HTTP_429_TOO_MANY_REQUESTS
        if isinstance(exc, ProviderRateLimitError)
        else status.HTTP_504_GATEWAY_TIMEOUT
        if isinstance(exc, ProviderTimeoutError)
        else status.HTTP_503_SERVICE_UNAVAILABLE
        if isinstance(exc, (ProviderConfigurationError, ProviderUnavailableError))
        else status.HTTP_502_BAD_GATEWAY
        if isinstance(exc, ProviderResponseError)
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


@router.get("/providers/map/status", response_model=ProviderStatusResponse)
async def get_map_provider_status(
    _: CurrentUserDep,
    settings: SettingsDep,
) -> ProviderStatusResponse:
    profile = settings.effective_map_provider_profile
    return ProviderStatusResponse(
        profile=profile,
        provider="mock" if profile == "mock" else "amap",
        configured=(
            profile == "mock"
            or settings.amap_web_service_key is not None
        ),
        capabilities=["search", "detail", "geocode", "route"],
    )


@router.get("/places/search", response_model=PlaceSearchResponse)
async def search_places(
    q: Annotated[str, Query(min_length=1, max_length=120)],
    _: CurrentUserDep,
    _map_feature: MapFeatureDep,
    service: PlaceServiceDep,
    city: Annotated[str | None, Query(max_length=80)] = None,
    types: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> PlaceSearchResponse:
    try:
        outcome = await service.search(
            PlaceQuery(keyword=q, city=city, types=types, limit=limit)
        )
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc
    return PlaceSearchResponse(
        provider=outcome.provider,
        profile=outcome.profile,
        cached=outcome.cached,
        results=[PlaceResponse.model_validate(item) for item in outcome.results],
    )


@router.get("/places/geocode", response_model=GeocodeResponse)
async def geocode(
    address: Annotated[str, Query(min_length=1, max_length=300)],
    _: CurrentUserDep,
    _map_feature: MapFeatureDep,
    service: PlaceServiceDep,
) -> GeocodeResponse:
    try:
        point = await service.geocode(address)
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc
    return GeocodeResponse.model_validate(point)


@router.get("/places/{provider_place_id}", response_model=PlaceResponse)
async def get_place(
    provider_place_id: str,
    _: CurrentUserDep,
    _map_feature: MapFeatureDep,
    service: PlaceServiceDep,
) -> PlaceResponse:
    try:
        place = await service.get(provider_place_id)
    except PlaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found",
        ) from exc
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc
    return PlaceResponse.model_validate(place)
