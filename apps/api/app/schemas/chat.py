# 文件说明：Pydantic 数据契约：chat。
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.requirement import TripBriefExtraction
from app.schemas.trip import TripBriefPayload

TravelIntent = Literal[
    "plan_trip",
    "travel_question",
    "destination_research",
    "route_advice",
    "budget_advice",
    "clarify",
    "out_of_scope",
]


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class TravelChatRequest(BaseModel):
    message: str = Field(default="", max_length=50_000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=3)
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_message_or_attachment(self) -> Self:
        if not self.message.strip() and not self.attachment_ids:
            raise ValueError("message or attachment_ids is required")
        return self


class ChatSourceCitation(BaseModel):
    url: str
    title: str | None = None
    cited_text: str | None = None
    published_at: str | None = None


class TravelChatResponse(BaseModel):
    intent: TravelIntent
    in_scope: bool
    confidence: float = Field(ge=0, le=1)
    answer: str | None = None
    sources: list[ChatSourceCitation] = Field(default_factory=list)
    selected_skills: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    requires_planning: bool = False
    brief: TripBriefPayload | None = None
    draft: TripBriefExtraction | None = None
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    model_name: str = ""
