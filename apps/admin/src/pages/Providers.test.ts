// 文件说明：管理后台页面测试：Providers。

import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { adminApi } from "../api";
import Providers from "./Providers.vue";

vi.mock("../api", () => ({
  adminApi: {
    providers: vi.fn(),
    features: vi.fn(),
    mcpConnectors: vi.fn(),
    toolHealth: vi.fn(),
    toggleMcpConnector: vi.fn(),
    toggleFeature: vi.fn(),
  },
}));

const connector = {
  connector_id: "amap",
  display_name: "高德地点 MCP",
  purpose: "真实地点搜索",
  boundary: "固定服务端 endpoint",
  tools: ["search_places"],
  configured: true,
  enabled: false,
  status: "disabled" as const,
  latency_ms: 0,
  last_error_code: null,
  checked_at: null,
  requests_today: 12,
  daily_quota: 1000,
  rate_limit_per_minute: 60,
  window_calls: 2,
  as_of: "2026-11-15T00:00:00Z",
};

describe("Providers admin page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminApi.providers).mockResolvedValue([]);
    vi.mocked(adminApi.features).mockResolvedValue([]);
    vi.mocked(adminApi.mcpConnectors).mockResolvedValue([connector]);
    vi.mocked(adminApi.toolHealth).mockResolvedValue([
      {
        tool_name: "search_places",
        provider: "amap",
        status: "healthy",
        invocations: 8,
        failed_invocations: 0,
        average_latency_ms: 180,
        last_error_code: null,
        checked_at: "2026-11-15T00:00:00Z",
      },
    ]);
    vi.mocked(adminApi.toggleMcpConnector).mockResolvedValue({
      ...connector,
      enabled: true,
      status: "configured",
    });
  });

  it("shows connector quota and enables a disabled connector", async () => {
    const wrapper = mount(Providers, {
      props: { token: "token" },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("MCP Connectors");
    expect(wrapper.text()).toContain("AMap");
    expect(wrapper.text()).toContain("12 / 1000");
    expect(wrapper.text()).toContain("search_places");

    const enableButton = wrapper.findAll("button").find((button) =>
      button.text().includes("启用 Connector")
    );
    expect(enableButton).toBeTruthy();
    await enableButton?.trigger("click");
    await flushPromises();

    expect(adminApi.toggleMcpConnector).toHaveBeenCalledWith(
      "token",
      "amap",
      true,
      "mcp connector enabled from admin",
    );
  });
});
