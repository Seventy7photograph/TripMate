# 文件说明：FastAPI 路由：conversations。
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    ConversationUpdateRequest,
)
from app.services.conversation_service import (
    ConversationConflictError,
    ConversationNotFoundError,
    ConversationService,
    ConversationTripNotFoundError,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(session: SessionDep) -> ConversationService:
    return ConversationService(session)


ConversationServiceDep = Annotated[
    ConversationService,
    Depends(get_conversation_service),
]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationResponse:
    try:
        conversation = await service.create(owner_id=current_user.id, payload=payload)
    except ConversationTripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    return ConversationResponse.model_validate(conversation)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationListResponse:
    items = await service.list(owner_id=current_user.id)
    return ConversationListResponse(
        items=[
            ConversationSummaryResponse.model_validate(item)
            for item in items
        ]
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationResponse:
    try:
        conversation = await service.get(
            owner_id=current_user.id,
            conversation_id=conversation_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from exc
    return ConversationResponse.model_validate(conversation)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdateRequest,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationResponse:
    try:
        conversation = await service.update(
            owner_id=current_user.id,
            conversation_id=conversation_id,
            payload=payload,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from exc
    except ConversationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conversation_version_conflict",
                "message": "Conversation was updated by another session",
                "current_version": exc.current_version,
            },
        ) from exc
    except ConversationTripNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found",
        ) from exc
    return ConversationResponse.model_validate(conversation)
