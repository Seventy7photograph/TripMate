# 文件说明：Pydantic 数据契约：skill。
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.skills.manifest import SkillStatus


class SkillToggleRequest(BaseModel):
    enabled: bool
    version: str | None = Field(default=None, pattern=r"^\d+\.\d+\.\d+$")
    reason: str | None = Field(default=None, max_length=300)


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    available_versions: list[str]
    display_name: str
    purpose: str
    boundary: str
    surfaces: list[str]
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
    registered: bool
    runtime_status: Literal["ready", "degraded", "disabled", "unavailable"]
    execution_mode: Literal["mcp", "local", "disabled"]
    recent_runs: int
    success_rate: float | None
    last_used_at: datetime | None
    as_of: datetime


class SkillListResponse(BaseModel):
    items: list[SkillResponse]
