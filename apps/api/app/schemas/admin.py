# 文件说明：Pydantic 数据契约：admin。
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)

FeatureFlagKey = Literal[
    "ai_planning",
    "brief_parsing",
    "llm_provider",
    "map_provider",
    "travel_chat",
    "agent_skills_enabled",
    "agent_skill_router_enabled",
    "mcp_gateway_enabled",
    "weather_provider",
]
ProviderDisplayStatus = Literal[
    "healthy",
    "degraded",
    "unavailable",
    "disabled",
    "configured",
    "unknown",
]
ModelStage = Literal[
    "brief_parse",
    "research_planner",
    "itinerary_composer",
    "travel_chat",
]


class FeatureToggleRequest(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=300)


class FeatureFlagResponse(BaseModel):
    key: FeatureFlagKey
    label: str
    description: str
    enabled: bool
    updated_by: UUID | None
    updated_at: datetime | None


class FeatureFlagListResponse(BaseModel):
    items: list[FeatureFlagResponse]


class AdminAgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by: UUID
    trip_id: UUID | None
    purpose: str
    status: str
    provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    tool_call_count: int
    loop_count: int
    skills_used: list[dict[str, object]]
    prompt_versions: list[dict[str, str]]
    skill_route: dict[str, object] | None
    estimated_cost_minor: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AdminAgentRunListResponse(BaseModel):
    items: list[AdminAgentRunResponse]
    total: int
    limit: int
    offset: int


class CostBreakdownItem(BaseModel):
    key: str
    runs: int
    failed_runs: int
    input_tokens: int
    output_tokens: int
    cost_minor: int


class DailyCostItem(BaseModel):
    date: date
    runs: int
    cost_minor: int


class CostLimitsResponse(BaseModel):
    user_daily_cost_minor: int
    ip_daily_cost_minor: int
    provider_daily_cost_minor: int
    run_cost_minor: int
    warning_ratio: float


class AdminCostSummaryResponse(BaseModel):
    window_days: int
    total_runs: int
    failed_runs: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_minor: int
    average_latency_ms: int
    by_provider: list[CostBreakdownItem]
    by_model: list[CostBreakdownItem]
    by_skill: list[CostBreakdownItem]
    daily: list[DailyCostItem]
    limits: CostLimitsResponse


class AdminToolHealthResponse(BaseModel):
    tool_name: str
    provider: str
    status: ProviderDisplayStatus
    invocations: int
    failed_invocations: int
    average_latency_ms: int
    last_error_code: str | None
    checked_at: datetime


class AdminToolHealthListResponse(BaseModel):
    items: list[AdminToolHealthResponse]


class AdminProviderResponse(BaseModel):
    key: FeatureFlagKey
    provider_type: str
    provider_name: str
    profile: str
    configured: bool
    enabled: bool
    status: ProviderDisplayStatus
    latency_ms: int
    invocations: int
    failed_invocations: int
    average_latency_ms: int
    last_error_code: str | None
    last_checked_at: datetime | None
    configuration: dict[str, object]


class AdminProviderListResponse(BaseModel):
    items: list[AdminProviderResponse]


class McpConnectorToggleRequest(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=300)


class AdminMcpConnectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    connector_id: str
    enabled: bool
    status: ProviderDisplayStatus
    latency_ms: int
    last_error_code: str | None
    checked_at: datetime | None
    requests_today: int
    daily_quota: int
    rate_limit_per_minute: int
    window_calls: int


class AdminMcpConnectorListResponse(BaseModel):
    items: list[AdminMcpConnectorResponse]


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID
    action: str
    target_type: str
    target_id: str
    details: dict[str, object]
    created_at: datetime


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogResponse]
    total: int


class ModelConfigUpdateRequest(BaseModel):
    provider_profile: Literal["live"]
    base_url: str = Field(min_length=1, max_length=500)
    model_name: str = Field(min_length=1, max_length=160)
    api_key: SecretStr | None = None
    clear_api_key: bool = False
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an HTTP or HTTPS URL")
        return normalized

    @field_validator("model_name")
    @classmethod
    def normalize_model_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model_name cannot be blank")
        return normalized


class ModelConfigResponse(BaseModel):
    stage: ModelStage
    label: str
    provider_profile: Literal["mock", "live"]
    base_url: str
    model_name: str
    api_key_configured: bool
    timeout_seconds: int
    max_retries: int
    source: Literal["environment", "database"]
    updated_at: datetime | None


class ModelConfigListResponse(BaseModel):
    items: list[ModelConfigResponse]
