# 文件说明：FastAPI 路由：places。
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_feature,
)
from app.domain.location import GeoPoint
from app.evidence.service import EvidenceService
from app.providers.base import (
    NearbyPlaceProvider,
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
from app.tools.base import ToolRunner
from app.tools.context import ToolContext
from app.tools.nearby_tools import NearbyPlacesOutput, NearbyTool
from app.tools.place_detail_tools import PlaceDetailOutput, PlaceDetailTool

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
    service: PlaceServiceDep,
) -> ProviderStatusResponse:
    status = await service.status()
    return ProviderStatusResponse(
        profile=status.profile,
        provider=status.provider,
        configured=status.configured,
        capabilities=status.capabilities,
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


@router.get("/places/nearby", response_model=NearbyPlacesOutput)
async def search_nearby_places(
    longitude: Annotated[float, Query(ge=-180, le=180)],
    latitude: Annotated[float, Query(ge=-90, le=90)],
    current_user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    _map_feature: MapFeatureDep,
    radius_m: Annotated[int, Query(ge=100, le=50_000)] = 2_000,
    types: Annotated[str, Query(max_length=300)] = "",
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> NearbyPlacesOutput:
    provider = create_map_provider(settings)
    if not hasattr(provider, "search_nearby"):
        close = getattr(provider, "close", None)
        if close is not None:
            await close()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "nearby_provider_unavailable",
                "message": "当前地图 Provider 不支持周边搜索",
            },
        )
    context = ToolContext(
        runner=ToolRunner(
            max_calls=2,
            deadline=datetime.now(UTC) + timedelta(seconds=20),
        ),
        allowed_tools={NearbyTool.name},
        provider_permissions={"map"},
        owner_id=current_user.id,
        evidence_writer=EvidenceService(session),
    )
    tool = NearbyTool(
        cast(NearbyPlaceProvider, provider),
        context,
    )
    try:
        result = await tool.search_nearby_places(
            location=GeoPoint(
                longitude=longitude,
                latitude=latitude,
            ),
            radius_m=radius_m,
            types=[
                item.strip()
                for item in types.split(",")
                if item.strip()
            ],
            limit=limit,
        )
        await session.commit()
        return result
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()
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


@router.get(
    "/places/{provider_place_id}/detail",
    response_model=PlaceDetailOutput,
)
async def get_place_detail(
    provider_place_id: str,
    current_user: CurrentUserDep,
    session: SessionDep,
    _map_feature: MapFeatureDep,
    service: PlaceServiceDep,
) -> PlaceDetailOutput:
    context = ToolContext(
        runner=ToolRunner(
            max_calls=2,
            deadline=datetime.now(UTC) + timedelta(seconds=20),
        ),
        allowed_tools={PlaceDetailTool.name},
        provider_permissions={"map"},
        owner_id=current_user.id,
        evidence_writer=EvidenceService(session),
    )
    tool = PlaceDetailTool(service, context)
    try:
        result = await tool.get_place_detail(provider_place_id)
        await session.commit()
        return result
    except PlaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Place not found",
        ) from exc
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc


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
