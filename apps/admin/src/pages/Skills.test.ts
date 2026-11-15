// 文件说明：管理后台页面测试：Skills。

import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { adminApi } from "../api";
import Skills from "./Skills.vue";

vi.mock("../api", () => ({
  adminApi: {
    skills: vi.fn(),
    toggleSkill: vi.fn(),
    auditLogs: vi.fn(),
    mcpConnectors: vi.fn(),
    checkMcpConnector: vi.fn(),
  },
}));

const skill = {
  name: "destination-research",
  available_versions: ["1.0.0"],
  display_name: "服务端目的地研究",
  purpose: "服务端真实用途说明",
  boundary: "服务端真实安全边界",
  runtime_status: "ready" as const,
  execution_mode: "mcp" as const,
  registered: true,
  recent_runs: 3,
  success_rate: 1,
  last_used_at: "2026-11-15T01:00:00Z",
  as_of: "2026-11-15T01:05:00Z",
  surfaces: ["travel_chat", "planning"],
  version: "1.0.0",
  status: "active" as const,
  description: "Research provider-backed destinations.",
  input_schema: { type: "object" },
  output_schema: { type: "object" },
  allowed_tools: ["search_places"],
  allowed_mcp_connectors: ["amap"],
  max_tool_calls: 4,
  timeout_seconds: 30,
  max_tokens: 4000,
  fallback: "existing_itinerary_graph",
  enabled: true,
  updated_by: "admin-1",
  updated_at: "2026-11-15T00:00:00Z",
};

describe("Skills admin page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminApi.skills).mockResolvedValue([skill]);
    vi.mocked(adminApi.auditLogs).mockResolvedValue({
      items: [
        {
          id: "audit-1",
          actor_id: "admin-1",
          action: "skill.toggle",
          target_type: "skill",
          target_id: "destination-research",
          details: { enabled: true, version: "1.0.0" },
          created_at: "2026-11-15T00:00:00Z",
        },
      ],
      total: 1,
    });
    vi.mocked(adminApi.mcpConnectors).mockResolvedValue([
      {
        connector_id: "amap",
        display_name: "服务端高德 MCP",
        purpose: "服务端 MCP 用途",
        boundary: "服务端 MCP 边界",
        tools: ["search_places"],
        configured: true,
        enabled: true,
        status: "healthy",
        latency_ms: 120,
        last_error_code: null,
        checked_at: "2026-11-15T00:00:00Z",
        requests_today: 12,
        daily_quota: 1000,
        rate_limit_per_minute: 60,
        window_calls: 2,
        as_of: "2026-11-15T01:05:00Z",
      },
    ]);
    vi.mocked(adminApi.checkMcpConnector).mockResolvedValue({
      connector_id: "amap",
      display_name: "服务端高德 MCP",
      purpose: "服务端 MCP 用途",
      boundary: "服务端 MCP 边界",
      tools: ["search_places"],
      configured: true,
      enabled: true,
      status: "healthy",
      latency_ms: 98,
      last_error_code: null,
      checked_at: "2026-11-15T01:06:00Z",
      requests_today: 12,
      daily_quota: 1000,
      rate_limit_per_minute: 60,
      window_calls: 2,
      as_of: "2026-11-15T01:06:00Z",
    });
    vi.mocked(adminApi.toggleSkill).mockResolvedValue({
      ...skill,
      enabled: false,
    });
  });

  it("shows manifest permissions and toggles a skill", async () => {
    const wrapper = mount(Skills, {
      props: { token: "token" },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Agent Skills");
    expect(wrapper.text()).toContain("destination-research");
    expect(wrapper.text()).toContain("search_places");
    expect(wrapper.text()).toContain("amap");
    expect(wrapper.text()).toContain("skill.toggle");
    expect(wrapper.text()).toContain("服务端目的地研究");
    expect(wrapper.text()).toContain("服务端真实用途说明");
    expect(wrapper.text()).toContain("服务端高德 MCP");

    const disableButton = wrapper.findAll("button").find((button) =>
      button.text().includes("停用 Skill")
    );
    await disableButton?.trigger("click");
    await flushPromises();

    expect(adminApi.toggleSkill).toHaveBeenCalledWith(
      "token",
      "destination-research",
      false,
      "skill disabled from admin",
      "1.0.0",
    );

    const checkButton = wrapper.findAll("button").find((button) =>
      button.text().includes("检测")
    );
    await checkButton?.trigger("click");
    await flushPromises();
    expect(adminApi.checkMcpConnector).toHaveBeenCalledWith("token", "amap");
  });


  it("refreshes runtime data automatically while the page is visible", async () => {
    vi.useFakeTimers();
    const wrapper = mount(Skills, {
      props: { token: "token" },
    });
    await flushPromises();
    expect(adminApi.skills).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5_000);
    await flushPromises();

    expect(adminApi.skills).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    vi.useRealTimers();
  });
});
