# 文件说明：FastAPI 路由：memories。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.memory import (
    MemoryCreateRequest,
    MemoryResponse,
    MemoryUpdateRequest,
)
from app.services.memory_service import (
    MemoryConsentRequired,
    MemoryNotFound,
    MemoryService,
)

router = APIRouter(prefix="/memories", tags=["memories"])


def get_memory_service(session: SessionDep) -> MemoryService:
    return MemoryService(session)


MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]


def memory_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Memory not found",
    )


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> list[MemoryResponse]:
    memories = await service.list_memories(owner_id=current_user.id)
    return [MemoryResponse.model_validate(memory) for memory in memories]


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory(
    payload: MemoryCreateRequest,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> MemoryResponse:
    try:
        memory = await service.create(owner_id=current_user.id, payload=payload)
    except MemoryConsentRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "memory_consent_required",
                "message": "Explicit user consent is required",
            },
        ) from exc
    return MemoryResponse.model_validate(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    payload: MemoryUpdateRequest,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> MemoryResponse:
    try:
        memory = await service.update(
            owner_id=current_user.id,
            memory_id=memory_id,
            payload=payload,
        )
    except MemoryNotFound as exc:
        raise memory_not_found() from exc
    return MemoryResponse.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> Response:
    try:
        await service.delete(owner_id=current_user.id, memory_id=memory_id)
    except MemoryNotFound as exc:
        raise memory_not_found() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_memories(
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> Response:
    await service.delete_all(owner_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
