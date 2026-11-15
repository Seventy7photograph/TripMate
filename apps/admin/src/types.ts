// 文件说明：管理后台模块：types。
export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "admin";
}

export interface AdminSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AdminUser;
}

export type FeatureFlagKey =
  | "ai_planning"
  | "brief_parsing"
  | "llm_provider"
  | "map_provider"
  | "travel_chat"
  | "agent_skills_enabled"
  | "agent_skill_router_enabled"
  | "mcp_gateway_enabled"
  | "weather_provider";

export interface FeatureFlag {
  key: FeatureFlagKey;
  label: string;
  description: string;
  enabled: boolean;
  updated_by: string | null;
  updated_at: string | null;
}

export interface AgentRun {
  id: string;
  created_by: string;
  trip_id: string | null;
  purpose: string;
  status: string;
  provider: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  tool_call_count: number;
  loop_count: number;
  estimated_cost_minor: number;
  skills_used: Array<{
    name: string;
    version: string;
    status: string;
  }>;
  prompt_versions: Array<{
    agent: string;
    prompt_id: string;
    version: string;
    sha256: string;
  }>;
  skill_route: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AgentRunList {
  items: AgentRun[];
  total: number;
  limit: number;
  offset: number;
}

export interface CostBreakdown {
  key: string;
  runs: number;
  failed_runs: number;
  input_tokens: number;
  output_tokens: number;
  cost_minor: number;
}

export interface DailyCost {
  date: string;
  runs: number;
  cost_minor: number;
}

export interface CostLimits {
  user_daily_cost_minor: number;
  ip_daily_cost_minor: number;
  provider_daily_cost_minor: number;
  run_cost_minor: number;
  warning_ratio: number;
}

export interface CostSummary {
  window_days: number;
  total_runs: number;
  failed_runs: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_minor: number;
  average_latency_ms: number;
  by_provider: CostBreakdown[];
  by_model: CostBreakdown[];
  by_skill: CostBreakdown[];
  daily: DailyCost[];
  limits: CostLimits;
}

export interface ToolHealth {
  tool_name: string;
  provider: string;
  status:
    | "healthy"
    | "degraded"
    | "unavailable"
    | "disabled"
    | "configured"
    | "unknown";
  invocations: number;
  failed_invocations: number;
  average_latency_ms: number;
  last_error_code: string | null;
  checked_at: string;
}

export interface SkillManifest {
  name: string;
  available_versions: string[];
  display_name: string;
  purpose: string;
  boundary: string;
  surfaces: string[];
  version: string;
  status: "active" | "disabled";
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  allowed_tools: string[];
  allowed_mcp_connectors: string[];
  max_tool_calls: number;
  timeout_seconds: number;
  max_tokens: number;
  fallback: string;
  enabled: boolean;
  updated_by: string | null;
  updated_at: string | null;
  registered: boolean;
  runtime_status: "ready" | "degraded" | "disabled" | "unavailable";
  execution_mode: "mcp" | "local" | "disabled";
  recent_runs: number;
  success_rate: number | null;
  last_used_at: string | null;
  as_of: string;
}

export interface ProviderStatus {
  key: FeatureFlagKey;
  provider_type: string;
  provider_name: string;
  profile: string;
  configured: boolean;
  enabled: boolean;
  status:
    | "healthy"
    | "degraded"
    | "unavailable"
    | "disabled"
    | "configured"
    | "unknown";
  latency_ms: number;
  invocations: number;
  failed_invocations: number;
  average_latency_ms: number;
  last_error_code: string | null;
  last_checked_at: string | null;
  configuration: Record<string, unknown>;
}

export interface McpConnectorStatus {
  connector_id: string;
  display_name: string;
  purpose: string;
  boundary: string;
  tools: string[];
  configured: boolean;
  enabled: boolean;
  status:
    | "healthy"
    | "degraded"
    | "unavailable"
    | "disabled"
    | "configured"
    | "unknown";
  latency_ms: number;
  last_error_code: string | null;
  checked_at: string | null;
  requests_today: number;
  daily_quota: number;
  rate_limit_per_minute: number;
  window_calls: number;
  as_of: string | null;
}

export interface AuditLog {
  id: string;
  actor_id: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLog[];
  total: number;
}

export type ModelStage =
  | "brief_parse"
  | "research_planner"
  | "itinerary_composer"
  | "travel_chat";

export interface ModelConfig {
  stage: ModelStage;
  label: string;
  provider_profile: "mock" | "live";
  base_url: string;
  model_name: string;
  api_key_configured: boolean;
  timeout_seconds: number;
  max_retries: number;
  source: "environment" | "database";
  updated_at: string | null;
}

export interface ModelConfigUpdate {
  provider_profile: "live";
  base_url: string;
  model_name: string;
  api_key?: string;
  clear_api_key?: boolean;
  timeout_seconds: number;
  max_retries: number;
}
