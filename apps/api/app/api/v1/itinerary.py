# 文件说明：FastAPI 路由：itinerary。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.itinerary import (
    ItineraryResponse,
    ItineraryStopCreateRequest,
    ItineraryStopResponse,
    ItineraryStopUpdateRequest,
    ReorderStopsRequest,
    TripDayCreateRequest,
    TripDayResponse,
)
from app.services.itinerary_service import (
    DayAlreadyExistsError,
    InvalidItineraryError,
    ItineraryNotFoundError,
    ItineraryService,
)
from app.services.version_service import VersionConflictError

router = APIRouter(tags=["itinerary"])


def get_itinerary_service(session: SessionDep) -> ItineraryService:
    return ItineraryService(session)


ItineraryServiceDep = Annotated[ItineraryService, Depends(get_itinerary_service)]


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def version_conflict(exc: VersionConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "version_conflict",
            "message": "Trip was updated by another session",
            "current_version": exc.current_version,
        },
    )


@router.get("/trips/{trip_id}/itinerary", response_model=ItineraryResponse)
async def get_itinerary(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: ItineraryServiceDep,
) -> ItineraryResponse:
    try:
        itinerary = await service.get(owner_id=current_user.id, trip_id=trip_id)
    except ItineraryNotFoundError as exc:
        raise not_found("Trip not found") from exc
    return ItineraryResponse.model_validate(itinerary)


@router.post(
    "/trips/{trip_id}/days",
    response_model=TripDayResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_day(
    trip_id: UUID,
    payload: TripDayCreateRequest,
    current_user: CurrentUserDep,
    service: ItineraryServiceDep,
) -> TripDayResponse:
    try:
        day = await service.create_day(
            owner_id=current_user.id,
            trip_id=trip_id,
            expected_version=payload.expected_version,
            day_date=payload.date,
            theme=payload.theme,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except ItineraryNotFoundError as exc:
        raise not_found("Trip not found") from exc
    except DayAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trip day already exists",
        ) from exc
    except InvalidItineraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return TripDayResponse.model_validate(day)


@router.post(
    "/days/{day_id}/stops",
    response_model=ItineraryStopResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stop(
    day_id: UUID,
    payload: ItineraryStopCreateRequest,
    current_user: CurrentUserDep,
    service: ItineraryServiceDep,
) -> ItineraryStopResponse:
    try:
        stop = await service.create_stop(
            owner_id=current_user.id,
            day_id=day_id,
            expected_version=payload.expected_version,
            place_id=payload.place_id,
            place_name=payload.place_name,
            start_at=payload.start_at,
            duration_minutes=payload.duration_minutes,
            estimated_cost_minor=payload.estimated_cost_minor,
            location=payload.location.to_domain() if payload.location else None,
            source=payload.source.to_domain() if payload.source else None,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except ItineraryNotFoundError as exc:
        raise not_found("Trip day not found") from exc
    except InvalidItineraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return ItineraryStopResponse.model_validate(stop)


@router.patch("/stops/{stop_id}", response_model=ItineraryStopResponse)
async def update_stop(
    stop_id: UUID,
    payload: ItineraryStopUpdateRequest,
    current_user: CurrentUserDep,
    service: ItineraryServiceDep,
) -> ItineraryStopResponse:
    try:
        stop = await service.update_stop(
            owner_id=current_user.id,
            stop_id=stop_id,
            expected_version=payload.expected_version,
            place_id=payload.place_id,
            place_name=payload.place_name,
            set_place_name="place_name" in payload.model_fields_set,
            start_at=payload.start_at,
            duration_minutes=payload.duration_minutes,
            estimated_cost_minor=payload.estimated_cost_minor,
            location=payload.location.to_domain() if payload.location else None,
            set_location="location" in payload.model_fields_set,
            source=payload.source.to_domain() if payload.source else None,
            set_source="source" in payload.model_fields_set,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except ItineraryNotFoundError as exc:
        raise not_found("Stop not found") from exc
    except InvalidItineraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return ItineraryStopResponse.model_validate(stop)


@router.delete("/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stop(
    stop_id: UUID,
    current_user: CurrentUserDep,
    service: ItineraryServiceDep,
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    try:
        await service.delete_stop(
            owner_id=current_user.id,
            stop_id=stop_id,
            expected_version=expected_version,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except ItineraryNotFoundError as exc:
        raise not_found("Stop not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/days/{day_id}/stops/reorder", response_model=TripDayResponse)
async def reorder_stops(
    day_id: UUID,
    payload: ReorderStopsRequest,
    current_user: CurrentUserDep,
    service: ItineraryServiceDep,
) -> TripDayResponse:
    try:
        day = await service.reorder_stops(
            owner_id=current_user.id,
            day_id=day_id,
            expected_version=payload.expected_version,
            stop_ids=payload.stop_ids,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except ItineraryNotFoundError as exc:
        raise not_found("Trip day not found") from exc
    except InvalidItineraryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return TripDayResponse.model_validate(day)
