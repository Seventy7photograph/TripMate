# 文件说明：FastAPI 路由：routes。
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_feature,
)
from app.providers.base import (
    ProviderConfigurationError,
    ProviderError,
    ProviderModeUnsupportedError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RouteMode,
)
from app.schemas.route import (
    RouteCalculateRequest,
    RouteCalculationResponse,
    RouteLegErrorResponse,
    RouteLegResponse,
)
from app.services.place_service import create_map_provider
from app.services.route_service import (
    InvalidRouteRequestError,
    RouteNotFoundError,
    RouteService,
)
from app.services.version_service import VersionConflictError

router = APIRouter(tags=["routes"])


async def get_route_service(
    session: SessionDep,
    settings: SettingsDep,
) -> AsyncIterator[RouteService]:
    provider = create_map_provider(settings)
    service = RouteService(session, settings, provider)
    try:
        yield service
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()


RouteServiceDep = Annotated[RouteService, Depends(get_route_service)]
MapFeatureDep = Annotated[None, Depends(require_feature("map_provider"))]


def version_conflict(exc: VersionConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "version_conflict",
            "message": "Trip was updated by another session",
            "current_version": exc.current_version,
        },
    )


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
    if isinstance(exc, ProviderModeUnsupportedError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


@router.post(
    "/trips/{trip_id}/days/{day_id}/routes",
    response_model=RouteCalculationResponse,
)
async def calculate_routes(
    trip_id: UUID,
    day_id: UUID,
    payload: RouteCalculateRequest,
    current_user: CurrentUserDep,
    _map_feature: MapFeatureDep,
    service: RouteServiceDep,
) -> RouteCalculationResponse:
    try:
        outcome = await service.calculate(
            owner_id=current_user.id,
            trip_id=trip_id,
            day_id=day_id,
            expected_version=payload.expected_version,
            stop_ids=payload.stop_ids,
            mode=payload.mode,
            modes=payload.modes,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except RouteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip day not found",
        ) from exc
    except InvalidRouteRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc
    return RouteCalculationResponse(
        legs=[RouteLegResponse.model_validate(leg) for leg in outcome.legs],
        errors=[
            RouteLegErrorResponse.model_validate(error)
            for error in outcome.errors
        ],
        modes=outcome.modes,
    )


@router.get("/trips/{trip_id}/days/{day_id}/map")
async def render_day_map(
    trip_id: UUID,
    day_id: UUID,
    current_user: CurrentUserDep,
    _map_feature: MapFeatureDep,
    service: RouteServiceDep,
    expected_version: Annotated[int, Query(ge=1)],
    mode: RouteMode = "driving",
    zoom: Annotated[int, Query(ge=3, le=17)] = 14,
    include_route: bool = True,
) -> Response:
    try:
        outcome = await service.render_map(
            owner_id=current_user.id,
            trip_id=trip_id,
            day_id=day_id,
            expected_version=expected_version,
            mode=mode,
            zoom=zoom,
            include_route=include_route,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except RouteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip day not found",
        ) from exc
    except ProviderError as exc:
        raise provider_http_exception(exc) from exc
    return Response(
        content=outcome.image.content,
        media_type=outcome.image.media_type,
        headers={
            "Cache-Control": "private, max-age=60",
            "X-Route-Available": "true" if outcome.route_available else "false",
        },
    )
