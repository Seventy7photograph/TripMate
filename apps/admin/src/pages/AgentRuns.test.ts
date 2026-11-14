// 文件说明：管理后台页面测试：AgentRuns。

import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { adminApi } from "../api";
import AgentRuns from "./AgentRuns.vue";

vi.mock("../api", () => ({
  adminApi: {
    agentRuns: vi.fn(),
  },
}));

describe("AgentRuns admin page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(adminApi.agentRuns).mockResolvedValue({
      items: [
        {
          id: "run-1",
          created_by: "user-1",
          trip_id: null,
          purpose: "planning",
          status: "completed",
          provider: "deepseek",
          model_name: "deepseek-flash",
          input_tokens: 100,
          output_tokens: 50,
          latency_ms: 900,
          tool_call_count: 4,
          loop_count: 0,
          estimated_cost_minor: 120,
          skills_used: [
            {
              name: "destination-research",
              version: "1.0.0",
              status: "completed",
            },
          ],
          prompt_versions: [],
          skill_route: {
            confidence: 0.93,
            fallback_reason: "router unavailable",
          },
          error_code: null,
          error_message: null,
          started_at: null,
          finished_at: null,
          created_at: "2026-11-15T00:00:00Z",
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
  });

  it("shows skill versions, router confidence and fallback reason", async () => {
    const wrapper = mount(AgentRuns, {
      props: { token: "token" },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("destination-research@1.0.0");
    expect(wrapper.text()).toContain("router 93.0%");
    expect(wrapper.text()).toContain("router unavailable");
    expect(wrapper.text()).toContain("4 / 0");
  });
});
