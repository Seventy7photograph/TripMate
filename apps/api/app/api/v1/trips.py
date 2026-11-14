# 文件说明：FastAPI 路由：trips。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.trip import (
    TripCreateRequest,
    TripResponse,
    TripUpdateRequest,
)
from app.schemas.version import RestoreVersionRequest, TripVersionHistoryResponse
from app.services.trip_service import TripNotFoundError, TripService
from app.services.version_service import (
    VersionConflictError,
    VersionNotFoundError,
    VersionService,
    VersionTripNotFoundError,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def get_trip_service(session: SessionDep) -> TripService:
    return TripService(session)


TripServiceDep = Annotated[TripService, Depends(get_trip_service)]


def get_version_service(session: SessionDep) -> VersionService:
    return VersionService(session)


VersionServiceDep = Annotated[VersionService, Depends(get_version_service)]


def version_conflict(exc: VersionConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "version_conflict",
            "message": "Trip was updated by another session",
            "current_version": exc.current_version,
        },
    )


@router.post(
    "",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trip(
    payload: TripCreateRequest,
    current_user: CurrentUserDep,
    service: TripServiceDep,
) -> TripResponse:
    trip = await service.create(
        owner_id=current_user.id,
        brief=payload.brief.to_domain(),
    )
    return TripResponse.model_validate(trip)


@router.get("", response_model=list[TripResponse])
async def list_trips(
    current_user: CurrentUserDep,
    service: TripServiceDep,
    include_archived: bool = False,
) -> list[TripResponse]:
    trips = await service.list(
        owner_id=current_user.id,
        include_archived=include_archived,
    )
    return [TripResponse.model_validate(trip) for trip in trips]


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: TripServiceDep,
) -> TripResponse:
    try:
        trip = await service.get(owner_id=current_user.id, trip_id=trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    return TripResponse.model_validate(trip)


@router.patch("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: UUID,
    payload: TripUpdateRequest,
    current_user: CurrentUserDep,
    service: TripServiceDep,
) -> TripResponse:
    try:
        trip = await service.update(
            owner_id=current_user.id,
            trip_id=trip_id,
            expected_version=payload.expected_version,
            brief=payload.brief.to_domain() if payload.brief is not None else None,
            status=payload.status,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    return TripResponse.model_validate(trip)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_trip(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: TripServiceDep,
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    try:
        await service.archive(
            owner_id=current_user.id,
            trip_id=trip_id,
            expected_version=expected_version,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except TripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{trip_id}/versions", response_model=TripVersionHistoryResponse)
async def list_trip_versions(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: VersionServiceDep,
) -> TripVersionHistoryResponse:
    try:
        history = await service.list_versions(
            owner_id=current_user.id,
            trip_id=trip_id,
        )
    except VersionTripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    return TripVersionHistoryResponse.model_validate(history)


@router.post("/{trip_id}/versions/{version}/restore", response_model=TripResponse)
async def restore_trip_version(
    trip_id: UUID,
    version: int,
    payload: RestoreVersionRequest,
    current_user: CurrentUserDep,
    version_service: VersionServiceDep,
    trip_service: TripServiceDep,
) -> TripResponse:
    try:
        await version_service.restore(
            owner_id=current_user.id,
            trip_id=trip_id,
            version=version,
            expected_version=payload.expected_version,
            created_by=current_user.id,
        )
        trip = await trip_service.get(owner_id=current_user.id, trip_id=trip_id)
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except VersionTripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    except VersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip version not found",
        ) from exc
    return TripResponse.model_validate(trip)
