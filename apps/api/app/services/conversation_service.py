# 文件说明：业务服务：conversation_service。
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation as ConversationModel
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessage,
    ConversationSummaryResponse,
    ConversationUpdateRequest,
)


class ConversationNotFoundError(Exception):
    pass


class ConversationTripNotFoundError(Exception):
    pass


class ConversationConflictError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("Conversation version conflict")
        self.current_version = current_version


@dataclass(frozen=True, slots=True)
class ConversationView:
    id: UUID
    title: str
    messages: list[ConversationMessage]
    requirement_history: list[str]
    trip_id: UUID | None
    version: int
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._conversations = ConversationRepository(session)
        self._trips = TripRepository(session)

    async def create(
        self,
        *,
        owner_id: UUID,
        payload: ConversationCreateRequest,
    ) -> ConversationView:
        if payload.trip_id is not None:
            await self._require_owned_trip(owner_id=owner_id, trip_id=payload.trip_id)
        messages = [message.model_dump(mode="json") for message in payload.messages]
        model = ConversationModel(
            owner_id=owner_id,
            trip_id=payload.trip_id,
            title=self._title(payload.title, payload.messages),
            messages=messages,
            requirement_history=payload.requirement_history,
            version=1,
        )
        self._conversations.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return self._view(model)

    async def update(
        self,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        payload: ConversationUpdateRequest,
    ) -> ConversationView:
        model = await self._conversations.get_for_owner(
            owner_id=owner_id,
            conversation_id=conversation_id,
            for_update=True,
        )
        if model is None:
            raise ConversationNotFoundError
        if model.version != payload.expected_version:
            raise ConversationConflictError(model.version)
        if payload.trip_id is not None:
            await self._require_owned_trip(owner_id=owner_id, trip_id=payload.trip_id)

        model.title = self._title(payload.title, payload.messages)
        model.messages = [message.model_dump(mode="json") for message in payload.messages]
        model.requirement_history = payload.requirement_history
        model.trip_id = payload.trip_id
        model.version += 1
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return self._view(model)

    async def get(
        self,
        *,
        owner_id: UUID,
        conversation_id: UUID,
    ) -> ConversationView:
        model = await self._conversations.get_for_owner(
            owner_id=owner_id,
            conversation_id=conversation_id,
        )
        if model is None:
            raise ConversationNotFoundError
        return self._view(model)

    async def list(
        self,
        *,
        owner_id: UUID,
    ) -> list[ConversationSummaryResponse]:
        models = await self._conversations.list_for_owner(owner_id=owner_id)
        return [self._summary(model) for model in models]

    async def _require_owned_trip(self, *, owner_id: UUID, trip_id: UUID) -> None:
        trip = await self._trips.get_for_owner(owner_id=owner_id, trip_id=trip_id)
        if trip is None:
            raise ConversationTripNotFoundError

    @staticmethod
    def _title(title: str, messages: Sequence[ConversationMessage]) -> str:
        normalized = title.strip()
        if normalized:
            return normalized
        first_user = next(
            (
                message.text.strip()
                for message in messages
                if message.role == "user" and message.text and message.text.strip()
            ),
            "",
        )
        if not first_user:
            first_attachment = next(
                (
                    message.attachments[0].name
                    for message in messages
                    if message.role == "user" and message.attachments
                ),
                "",
            )
            first_user = first_attachment
        return first_user[:80] or "新的旅行对话"

    @staticmethod
    def _preview(model: ConversationModel) -> str:
        for message in reversed(model.messages):
            text = message.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()[:120]
            attachments = message.get("attachments")
            if isinstance(attachments, list) and attachments:
                first = attachments[0]
                if isinstance(first, dict) and isinstance(first.get("name"), str):
                    return str(first["name"])[:120]
        return "还没有对话内容"

    @classmethod
    def _summary(cls, model: ConversationModel) -> ConversationSummaryResponse:
        return ConversationSummaryResponse(
            id=model.id,
            title=model.title,
            trip_id=model.trip_id,
            version=model.version,
            message_count=len(model.messages),
            preview=cls._preview(model),
            updated_at=model.updated_at,
        )

    @staticmethod
    def _view(model: ConversationModel) -> ConversationView:
        return ConversationView(
            id=model.id,
            title=model.title,
            messages=[
                ConversationMessage.model_validate(message)
                for message in model.messages
            ],
            requirement_history=list(model.requirement_history),
            trip_id=model.trip_id,
            version=model.version,
            message_count=len(model.messages),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
