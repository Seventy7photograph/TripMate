# 文件说明：FastAPI 路由：shares。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.share import (
    PublicTripResponse,
    ShareCreateRequest,
    ShareCreateResponse,
    ShareSummaryResponse,
    TripExportResponse,
)
from app.services.share_service import (
    ShareNotFoundError,
    ShareService,
    ShareTripNotFoundError,
)

router = APIRouter(tags=["shares"])


def get_share_service(session: SessionDep) -> ShareService:
    return ShareService(session)


ShareServiceDep = Annotated[ShareService, Depends(get_share_service)]


def share_trip_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Trip not found",
    )


@router.post(
    "/trips/{trip_id}/shares",
    response_model=ShareCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_share(
    trip_id: UUID,
    payload: ShareCreateRequest,
    current_user: CurrentUserDep,
    service: ShareServiceDep,
) -> ShareCreateResponse:
    try:
        share = await service.create(
            owner_id=current_user.id,
            trip_id=trip_id,
            expires_in_days=payload.expires_in_days,
        )
    except ShareTripNotFoundError as exc:
        raise share_trip_not_found() from exc
    return ShareCreateResponse(
        id=share.id,
        token=share.token,
        url_path=f"/share/{share.token}",
        expires_at=share.expires_at,
        created_at=share.created_at,
    )


@router.get(
    "/trips/{trip_id}/shares",
    response_model=list[ShareSummaryResponse],
)
async def list_shares(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: ShareServiceDep,
) -> list[ShareSummaryResponse]:
    try:
        shares = await service.list(owner_id=current_user.id, trip_id=trip_id)
    except ShareTripNotFoundError as exc:
        raise share_trip_not_found() from exc
    return [
        ShareSummaryResponse(
            id=item.id,
            trip_id=item.trip_id,
            status=service.status(item),  # type: ignore[arg-type]
            expires_at=item.expires_at,
            revoked_at=item.revoked_at,
            created_at=item.created_at,
        )
        for item in shares
    ]


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: UUID,
    current_user: CurrentUserDep,
    service: ShareServiceDep,
) -> Response:
    try:
        await service.revoke(owner_id=current_user.id, share_id=share_id)
    except ShareNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/public/trips/{token}",
    response_model=PublicTripResponse,
)
async def get_public_trip(token: str, service: ShareServiceDep) -> PublicTripResponse:
    try:
        snapshot = await service.public_snapshot(token=token)
    except ShareNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        ) from exc
    return PublicTripResponse.model_validate(snapshot)


@router.get(
    "/trips/{trip_id}/export",
    response_model=TripExportResponse,
)
async def export_trip(
    trip_id: UUID,
    current_user: CurrentUserDep,
    service: ShareServiceDep,
) -> TripExportResponse:
    try:
        document = await service.export_document(
            owner_id=current_user.id,
            trip_id=trip_id,
        )
    except ShareTripNotFoundError as exc:
        raise share_trip_not_found() from exc
    return TripExportResponse.model_validate(document)
