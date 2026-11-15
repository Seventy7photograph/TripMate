# 文件说明：Pydantic 数据契约：conversation。
import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.chat import ChatSourceCitation
from app.schemas.planning_draft import PlanningDraft

MAX_CONVERSATION_MESSAGES = 200
MAX_CONVERSATION_REQUIREMENTS = 200
MAX_CONVERSATION_BYTES = 2_000_000


def validate_transcript_size(
    messages: list["ConversationMessage"],
    requirement_history: list[str],
    planning_draft: PlanningDraft | None = None,
) -> None:
    payload = {
        "messages": [message.model_dump(mode="json") for message in messages],
        "requirement_history": requirement_history,
        "planning_draft": (
            None
            if planning_draft is None
            else planning_draft.model_dump(mode="json")
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    if len(encoded) > MAX_CONVERSATION_BYTES:
        raise ValueError("conversation transcript exceeds 2 MB")


class ConversationAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    kind: Literal["image", "document"]
    size_bytes: int = Field(ge=0)


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    role: Literal["user", "assistant"]
    kind: Literal["text", "questions", "working", "plan", "answer"]
    text: str | None = Field(default=None, max_length=50_000)
    questions: list[str] = Field(default_factory=list, max_length=20)
    draft: dict[str, Any] | None = None
    trip: dict[str, Any] | None = None
    itinerary: dict[str, Any] | None = None
    job: dict[str, Any] | None = None
    job_id: str | None = Field(default=None, max_length=160)
    map_day_id: str | None = Field(default=None, max_length=160)
    intent: str | None = Field(default=None, max_length=40)
    sources: list[ChatSourceCitation] = Field(default_factory=list, max_length=20)
    used_tools: list[str] = Field(default_factory=list, max_length=20)
    attachments: list[ConversationAttachment] = Field(
        default_factory=list,
        max_length=3,
    )


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=160)
    messages: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_CONVERSATION_MESSAGES,
    )
    requirement_history: list[str] = Field(
        default_factory=list,
        max_length=MAX_CONVERSATION_REQUIREMENTS,
    )
    planning_draft: PlanningDraft = Field(default_factory=PlanningDraft)
    trip_id: UUID | None = None

    @field_validator("requirement_history")
    @classmethod
    def validate_requirement_history(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 50_000 for value in normalized):
            raise ValueError("requirement history entries must be 1-50000 characters")
        return normalized

    @model_validator(mode="after")
    def validate_size(self) -> "ConversationCreateRequest":
        validate_transcript_size(
            self.messages,
            self.requirement_history,
            self.planning_draft,
        )
        return self


class ConversationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    title: str = Field(max_length=160)
    messages: list[ConversationMessage] = Field(
        max_length=MAX_CONVERSATION_MESSAGES,
    )
    requirement_history: list[str] = Field(
        max_length=MAX_CONVERSATION_REQUIREMENTS,
    )
    planning_draft: PlanningDraft | None = None
    trip_id: UUID | None = None

    @field_validator("requirement_history")
    @classmethod
    def validate_requirement_history(cls, values: list[str]) -> list[str]:
        return ConversationCreateRequest.validate_requirement_history(values)

    @model_validator(mode="after")
    def validate_size(self) -> "ConversationUpdateRequest":
        validate_transcript_size(
            self.messages,
            self.requirement_history,
            self.planning_draft,
        )
        return self


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    messages: list[ConversationMessage]
    requirement_history: list[str]
    planning_draft: dict[str, Any]
    trip_id: UUID | None
    version: int
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    trip_id: UUID | None
    planning_draft: dict[str, Any]
    version: int
    message_count: int
    preview: str
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationSummaryResponse]
