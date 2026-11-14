// 文件说明：管理后台模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { adminApi, ApiError } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const adminUser = {
  id: "admin-1",
  email: "admin@example.com",
  display_name: "Admin",
  role: "admin" as const,
};

describe("admin API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects a non-admin login response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          access_token: "token",
          token_type: "bearer",
          expires_in: 1800,
          user: { ...adminUser, role: "user" },
        }),
      ),
    );

    await expect(adminApi.login("user@example.com", "password")).rejects.toMatchObject({
      status: 403,
      message: "该账号没有管理权限",
    } satisfies Partial<ApiError>);
  });

  it("loads provider and feature controls with bearer auth", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              key: "llm_provider",
              provider_type: "llm",
              provider_name: "per-stage",
              profile: "live",
              configured: true,
              enabled: true,
              status: "configured",
              latency_ms: 0,
              invocations: 0,
              failed_invocations: 0,
              average_latency_ms: 0,
              last_error_code: null,
              last_checked_at: null,
              configuration: {},
            },
          ],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await adminApi.providers("token");
    await adminApi.features("token");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/admin/providers",
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((options.headers as Headers).get("Authorization")).toBe(
      "Bearer token",
    );
  });

  it("revokes the current admin token on logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await adminApi.logout("token");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("toggles a feature with the requested state and reason", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        key: "ai_planning",
        label: "AI 行程规划",
        description: "AI",
        enabled: false,
        updated_by: "admin-1",
        updated_at: "2026-11-14T00:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await adminApi.toggleFeature("token", "ai_planning", false, "maintenance");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/admin/features/ai_planning/toggle",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enabled: false, reason: "maintenance" }),
      }),
    );
  });

  it("loads and toggles MCP connectors", async () => {
    const connector = {
      connector_id: "amap",
      enabled: false,
      status: "disabled",
      latency_ms: 0,
      last_error_code: null,
      checked_at: null,
      requests_today: 12,
      daily_quota: 1000,
      rate_limit_per_minute: 60,
      window_calls: 3,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [connector] }))
      .mockResolvedValueOnce(
        jsonResponse({ ...connector, enabled: true, status: "configured" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const connectors = await adminApi.mcpConnectors("token");
    expect(connectors[0]?.connector_id).toBe("amap");
    await adminApi.toggleMcpConnector("token", "amap", true, "rollout");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/admin/mcp-connectors",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/admin/mcp-connectors/amap/toggle",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enabled: true, reason: "rollout" }),
      }),
    );
  });

  it("loads skill manifests and toggles a skill", async () => {
    const skill = {
      name: "destination-research",
      version: "1.0.0",
      status: "active",
      description: "Research destinations",
      input_schema: { type: "object" },
      output_schema: { type: "object" },
      allowed_tools: ["search_places"],
      allowed_mcp_connectors: ["amap"],
      max_tool_calls: 4,
      timeout_seconds: 30,
      max_tokens: 4000,
      fallback: "single_agent",
      enabled: true,
      updated_by: null,
      updated_at: null,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [skill] }))
      .mockResolvedValueOnce(
        jsonResponse({ ...skill, enabled: false }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const skills = await adminApi.skills("token");
    expect(skills[0]?.name).toBe("destination-research");
    await adminApi.toggleSkill("token", skill.name, false, "rollback");

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/admin/skills/destination-research/toggle",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enabled: false, reason: "rollback" }),
      }),
    );
  });

  it("loads local tool health metrics", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            tool_name: "search_places",
            provider: "amap",
            status: "healthy",
            invocations: 12,
            failed_invocations: 0,
            average_latency_ms: 180,
            last_error_code: null,
            checked_at: "2026-11-15T00:00:00Z",
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const tools = await adminApi.toolHealth("token");

    expect(tools[0]?.tool_name).toBe("search_places");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/admin/tool-health?hours=24",
      expect.any(Object),
    );
  });

  it("loads and updates stage-specific model configuration", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              stage: "brief_parse",
              label: "需求解析",
              provider_profile: "live",
              base_url: "https://api.example.test",
              model_name: "live-model",
              api_key_configured: true,
              timeout_seconds: 30,
              max_retries: 2,
              source: "environment",
              updated_at: null,
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          stage: "brief_parse",
          label: "需求解析",
          provider_profile: "live",
          base_url: "https://llm.example.test",
          model_name: "model-a",
          api_key_configured: true,
          timeout_seconds: 20,
          max_retries: 1,
          source: "database",
          updated_at: "2026-11-14T00:00:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const configs = await adminApi.modelConfigs("token");
    expect(configs[0]?.stage).toBe("brief_parse");
    await adminApi.updateModelConfig("token", "brief_parse", {
      provider_profile: "live",
      base_url: "https://llm.example.test",
      model_name: "model-a",
      api_key: "write-only",
      timeout_seconds: 20,
      max_retries: 1,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/admin/model-configs",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/admin/model-configs/brief_parse",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("write-only"),
      }),
    );
  });
});
