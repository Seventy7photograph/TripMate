# 文件说明：Pydantic 数据契约：skill。
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.skills.manifest import SkillStatus


class SkillToggleRequest(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=300)


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    version: str
    status: SkillStatus
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    allowed_tools: list[str]
    allowed_mcp_connectors: list[str]
    max_tool_calls: int
    timeout_seconds: float
    max_tokens: int
    fallback: str
    enabled: bool
    updated_by: UUID | None
    updated_at: datetime | None


class SkillListResponse(BaseModel):
    items: list[SkillResponse]
