# 文件说明：MCP Gateway 数据契约。

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

McpConnectorStatus = Literal[
    "healthy",
    "degraded",
    "unavailable",
    "disabled",
    "configured",
    "unknown",
]


class McpToolBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=80)
    provider_type: Literal["map", "weather"]


class McpConnectorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$", max_length=32)
    provider_type: Literal["map", "weather"]
    endpoint: str
    tools: tuple[McpToolBinding, ...]


class McpConnectionState(BaseModel):
    connector_id: str
    enabled: bool
    status: McpConnectorStatus
    latency_ms: int = Field(ge=0)
    last_error_code: str | None = None
    checked_at: datetime | None = None
    requests_today: int = Field(default=0, ge=0)
    daily_quota: int = Field(default=0, ge=0)
    rate_limit_per_minute: int = Field(default=0, ge=0)
    window_calls: int = Field(default=0, ge=0)


class McpRemoteResult(BaseModel):
    content: list[dict[str, object]] = Field(default_factory=list)
    structured_content: dict[str, object] | None = None
    is_error: bool = False


class McpToolResult(BaseModel):
    connector_id: str
    tool_name: str
    untrusted: Literal[True] = True
    content: list[dict[str, object]] = Field(default_factory=list)
    prompt_text: str
    data: dict[str, object]
    fallback_used: bool = False
