# 文件说明：FastAPI 路由：favorites。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.share import (
    FavoriteCreateRequest,
    FavoriteResponse,
    FavoriteUpdateRequest,
)
from app.services.favorite_service import (
    FavoriteNotFoundError,
    FavoriteService,
    FavoriteTargetNotFoundError,
)

router = APIRouter(prefix="/favorites", tags=["favorites"])


def get_favorite_service(session: SessionDep) -> FavoriteService:
    return FavoriteService(session)


FavoriteServiceDep = Annotated[FavoriteService, Depends(get_favorite_service)]


@router.post("", response_model=FavoriteResponse)
async def create_favorite(
    payload: FavoriteCreateRequest,
    response: Response,
    current_user: CurrentUserDep,
    service: FavoriteServiceDep,
) -> FavoriteResponse:
    try:
        favorite, created = await service.create(
            owner_id=current_user.id,
            payload=payload,
        )
    except FavoriteTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite target not found",
        ) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return FavoriteResponse.model_validate(favorite)


@router.get("", response_model=list[FavoriteResponse])
async def list_favorites(
    current_user: CurrentUserDep,
    service: FavoriteServiceDep,
    kind: Annotated[str | None, Query(pattern="^(place|trip)$")] = None,
    folder: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
) -> list[FavoriteResponse]:
    favorites = await service.list(
        owner_id=current_user.id,
        kind=kind,
        folder=folder,
    )
    return [FavoriteResponse.model_validate(item) for item in favorites]


@router.patch("/{favorite_id}", response_model=FavoriteResponse)
async def update_favorite(
    favorite_id: UUID,
    payload: FavoriteUpdateRequest,
    current_user: CurrentUserDep,
    service: FavoriteServiceDep,
) -> FavoriteResponse:
    try:
        favorite = await service.update(
            owner_id=current_user.id,
            favorite_id=favorite_id,
            payload=payload,
        )
    except FavoriteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        ) from exc
    return FavoriteResponse.model_validate(favorite)


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    favorite_id: UUID,
    current_user: CurrentUserDep,
    service: FavoriteServiceDep,
) -> Response:
    try:
        await service.remove(owner_id=current_user.id, favorite_id=favorite_id)
    except FavoriteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
