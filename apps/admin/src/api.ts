// 文件说明：管理后台模块：api。
import type {
  AdminSession,
  AdminUser,
  AgentRunList,
  AuditLogList,
  CostSummary,
  FeatureFlag,
  FeatureFlagKey,
  McpConnectorStatus,
  ModelConfig,
  ModelConfigUpdate,
  ModelStage,
  ProviderStatus,
  SkillManifest,
  ToolHealth,
} from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...options, headers });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : null;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" &&
            detail !== null &&
            "message" in detail &&
            typeof detail.message === "string"
          ? detail.message
          : "请求失败";
    throw new ApiError(response.status, message, detail);
  }
  return payload as T;
}

export const adminApi = {
  async login(email: string, password: string): Promise<AdminSession> {
    const session = await request<AdminSession>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (session.user.role !== "admin") {
      throw new ApiError(403, "该账号没有管理权限");
    }
    return session;
  },

  me(token: string): Promise<AdminUser> {
    return request<AdminUser>("/api/v1/auth/me", {}, token);
  },

  logout(token: string): Promise<unknown> {
    return request<unknown>(
      "/api/v1/auth/logout",
      { method: "POST" },
      token,
    );
  },

  agentRuns(
    token: string,
    filters: {
      status?: string;
      purpose?: string;
      provider?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<AgentRunList> {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return request<AgentRunList>(
      `/api/v1/admin/agent-runs?${query.toString()}`,
      {},
      token,
    );
  },

  costs(token: string, days = 30): Promise<CostSummary> {
    return request<CostSummary>(
      `/api/v1/admin/costs?days=${days}`,
      {},
      token,
    );
  },

  async providers(token: string): Promise<ProviderStatus[]> {
    const response = await request<{ items: ProviderStatus[] }>(
      "/api/v1/admin/providers",
      {},
      token,
    );
    return response.items;
  },

  async mcpConnectors(token: string): Promise<McpConnectorStatus[]> {
    const response = await request<{ items: McpConnectorStatus[] }>(
      "/api/v1/admin/mcp-connectors",
      {},
      token,
    );
    return response.items;
  },

  toggleMcpConnector(
    token: string,
    connectorId: string,
    enabled: boolean,
    reason?: string,
  ): Promise<McpConnectorStatus> {
    return request<McpConnectorStatus>(
      `/api/v1/admin/mcp-connectors/${encodeURIComponent(connectorId)}/toggle`,
      {
        method: "POST",
        body: JSON.stringify({ enabled, reason }),
      },
      token,
    );
  },

  async skills(token: string): Promise<SkillManifest[]> {
    const response = await request<{ items: SkillManifest[] }>(
      "/api/v1/admin/skills",
      {},
      token,
    );
    return response.items;
  },

  toggleSkill(
    token: string,
    skillName: string,
    enabled: boolean,
    reason?: string,
  ): Promise<SkillManifest> {
    return request<SkillManifest>(
      `/api/v1/admin/skills/${encodeURIComponent(skillName)}/toggle`,
      {
        method: "POST",
        body: JSON.stringify({ enabled, reason }),
      },
      token,
    );
  },

  async toolHealth(token: string, hours = 24): Promise<ToolHealth[]> {
    const response = await request<{ items: ToolHealth[] }>(
      `/api/v1/admin/tool-health?hours=${hours}`,
      {},
      token,
    );
    return response.items;
  },

  async features(token: string): Promise<FeatureFlag[]> {
    const response = await request<{ items: FeatureFlag[] }>(
      "/api/v1/admin/features",
      {},
      token,
    );
    return response.items;
  },

  toggleFeature(
    token: string,
    key: FeatureFlagKey,
    enabled: boolean,
    reason?: string,
  ): Promise<FeatureFlag> {
    return request<FeatureFlag>(
      `/api/v1/admin/features/${encodeURIComponent(key)}/toggle`,
      {
        method: "POST",
        body: JSON.stringify({ enabled, reason }),
      },
      token,
    );
  },

  auditLogs(token: string, limit = 20): Promise<AuditLogList> {
    return request<AuditLogList>(
      `/api/v1/admin/audit-logs?limit=${limit}`,
      {},
      token,
    );
  },

  async modelConfigs(token: string): Promise<ModelConfig[]> {
    const response = await request<{ items: ModelConfig[] }>(
      "/api/v1/admin/model-configs",
      {},
      token,
    );
    return response.items;
  },

  updateModelConfig(
    token: string,
    stage: ModelStage,
    input: ModelConfigUpdate,
  ): Promise<ModelConfig> {
    return request<ModelConfig>(
      `/api/v1/admin/model-configs/${encodeURIComponent(stage)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
      token,
    );
  },
};
