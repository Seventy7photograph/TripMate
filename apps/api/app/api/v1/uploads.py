# 文件说明：FastAPI 路由：uploads。
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.api.deps import CurrentUserDep, SessionDep, rate_limit
from app.core.config import Settings, get_settings
from app.schemas.upload import UploadedAssetResponse
from app.services.upload_service import (
    InvalidUpload,
    UnsupportedUpload,
    UploadMalwareDetected,
    UploadNotFound,
    UploadScannerUnavailable,
    UploadService,
    UploadTooLarge,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


def get_upload_service(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadService:
    return UploadService(session, settings)


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
UploadRateLimitDep = Annotated[
    None,
    Depends(
        rate_limit(
            scope="upload",
            limit_attribute="rate_limit_upload_per_minute",
        )
    ),
]


def upload_error(exc: Exception) -> HTTPException:
    if isinstance(exc, UploadTooLarge):
        code = status.HTTP_413_CONTENT_TOO_LARGE
    elif isinstance(exc, UnsupportedUpload):
        code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    elif isinstance(exc, UploadNotFound):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, UploadScannerUnavailable):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, UploadMalwareDetected):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = getattr(exc, "code", "invalid_upload_content")
    return HTTPException(
        status_code=code,
        detail={
            "code": error_code,
            "message": "文件未通过安全校验",
        },
    )


@router.post("", response_model=UploadedAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    current_user: CurrentUserDep,
    _rate_limit: UploadRateLimitDep,
    service: UploadServiceDep,
    file: Annotated[UploadFile, File()],
) -> UploadedAssetResponse:
    try:
        return await service.create(owner_id=current_user.id, upload=file)
    except (
        UploadTooLarge,
        UnsupportedUpload,
        InvalidUpload,
        UploadMalwareDetected,
        UploadScannerUnavailable,
    ) as exc:
        raise upload_error(exc) from exc


@router.get("/{asset_id}/content")
async def get_asset_content(
    asset_id: UUID,
    current_user: CurrentUserDep,
    service: UploadServiceDep,
) -> Response:
    try:
        asset = await service.get_owned(owner_id=current_user.id, asset_id=asset_id)
        content = await service.read_content(asset)
    except UploadNotFound as exc:
        raise upload_error(exc) from exc
    disposition = (
        "inline"
        if asset.kind == "image"
        else f"attachment; filename*=UTF-8''{quote(asset.original_name)}"
    )
    return Response(
        content=content,
        media_type=asset.mime_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    current_user: CurrentUserDep,
    service: UploadServiceDep,
) -> Response:
    try:
        await service.delete(owner_id=current_user.id, asset_id=asset_id)
    except UploadNotFound as exc:
        raise upload_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
