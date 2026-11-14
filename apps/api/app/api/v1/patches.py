# 文件说明：FastAPI 路由：patches。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.patch import (
    PatchActionRequest,
    PatchApplyResponse,
    PatchResponse,
    ReplanRequest,
)
from app.services.patch_service import (
    NoStopsToPatchError,
    PatchNotFoundError,
    PatchService,
    PatchStaleError,
    PatchStateError,
    UnsupportedReplanError,
)
from app.services.version_service import VersionConflictError

router = APIRouter(tags=["patches"])


def get_patch_service(session: SessionDep) -> PatchService:
    return PatchService(session)


PatchServiceDep = Annotated[PatchService, Depends(get_patch_service)]


def patch_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Itinerary patch not found",
    )


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
    "/trips/{trip_id}/replan",
    response_model=PatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_replan(
    trip_id: UUID,
    payload: ReplanRequest,
    current_user: CurrentUserDep,
    service: PatchServiceDep,
) -> PatchResponse:
    try:
        patch = await service.create_replan(
            owner_id=current_user.id,
            trip_id=trip_id,
            expected_version=payload.expected_version,
            day_id=payload.day_id,
            instruction=payload.instruction,
        )
    except PatchNotFoundError as exc:
        raise patch_not_found() from exc
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except NoStopsToPatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "no_stops_to_patch", "message": "目标日没有可重排地点"},
        ) from exc
    except UnsupportedReplanError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "unsupported_replan_instruction",
                "message": "首版支持删除指定数量或名称的地点",
            },
        ) from exc
    return PatchResponse.model_validate(patch)


@router.get(
    "/trips/{trip_id}/patches/{patch_id}",
    response_model=PatchResponse,
)
async def get_patch(
    trip_id: UUID,
    patch_id: UUID,
    current_user: CurrentUserDep,
    service: PatchServiceDep,
) -> PatchResponse:
    try:
        patch = await service.get(
            owner_id=current_user.id,
            trip_id=trip_id,
            patch_id=patch_id,
        )
    except PatchNotFoundError as exc:
        raise patch_not_found() from exc
    return PatchResponse.model_validate(patch)


@router.post(
    "/trips/{trip_id}/patches/{patch_id}/apply",
    response_model=PatchApplyResponse,
)
async def apply_patch(
    trip_id: UUID,
    patch_id: UUID,
    payload: PatchActionRequest,
    current_user: CurrentUserDep,
    service: PatchServiceDep,
) -> PatchApplyResponse:
    try:
        result = await service.apply(
            owner_id=current_user.id,
            trip_id=trip_id,
            patch_id=patch_id,
            expected_version=payload.expected_version,
        )
    except PatchNotFoundError as exc:
        raise patch_not_found() from exc
    except PatchStaleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "patch_stale",
                "message": "行程已更新，请重新生成局部重排",
                "current_version": exc.current_version,
            },
        ) from exc
    except PatchStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "patch_not_pending", "message": "该重排已处理"},
        ) from exc
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    return PatchApplyResponse.model_validate(
        {
            "id": result.patch.id,
            "trip_id": result.patch.trip_id,
            "target_day_id": result.patch.target_day_id,
            "base_version": result.patch.base_version,
            "applied_version": result.patch.applied_version,
            "status": result.patch.status,
            "instruction": result.patch.instruction,
            "changes": result.patch.changes,
            "created_at": result.patch.created_at,
            "applied_at": result.patch.applied_at,
            "itinerary": result.itinerary,
        }
    )


@router.post(
    "/trips/{trip_id}/patches/{patch_id}/discard",
    response_model=PatchResponse,
)
async def discard_patch(
    trip_id: UUID,
    patch_id: UUID,
    payload: PatchActionRequest,
    current_user: CurrentUserDep,
    service: PatchServiceDep,
) -> PatchResponse:
    try:
        patch = await service.discard(
            owner_id=current_user.id,
            trip_id=trip_id,
            patch_id=patch_id,
            expected_version=payload.expected_version,
        )
    except PatchNotFoundError as exc:
        raise patch_not_found() from exc
    except PatchStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "patch_not_pending", "message": "该重排已处理"},
        ) from exc
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    return PatchResponse.model_validate(patch)
