// 文件说明：前端页面：TripsView.test。
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { tripApi } from "../../features/trips/api";
import type { Trip } from "../../features/trips/types";
import { useAuthStore } from "../../stores/auth";
import TripsView from "./TripsView.vue";

vi.mock("../../features/trips/api", () => ({
  tripApi: {
    list: vi.fn(),
    archive: vi.fn(),
  },
}));

const trip: Trip = {
  id: "trip-1",
  owner_id: "user-1",
  status: "draft",
  version: 3,
  brief: {
    destination: "重庆",
    origin: "上海",
    start_date: "2026-12-01",
    end_date: "2026-12-03",
    party_size: 2,
    budget_minor: 500_000,
    currency: "CNY",
    interests: ["美食"],
    pace: "balanced",
    transport_preferences: [],
    transport_strategy: {
      strategy: "unspecified",
      segments: [],
      constraints: [],
    },
    lodging_preferences: [],
    must_visit: [],
    avoid: [],
    constraints: [],
  },
  created_at: "2026-11-14T00:00:00Z",
  updated_at: "2026-11-14T00:00:00Z",
};

describe("TripsView", () => {
  beforeEach(() => {
    sessionStorage.setItem("tripmate.access-token", "token");
    setActivePinia(createPinia());
    useAuthStore();
    vi.mocked(tripApi.list).mockResolvedValue([trip]);
    vi.mocked(tripApi.archive).mockResolvedValue();
  });

  it("deletes a trip after an explicit confirmation and refreshes the list", async () => {
    const wrapper = mount(TripsView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    await wrapper
      .get('button[aria-label="删除 重庆 旅行计划"]')
      .trigger("click");
    expect(wrapper.text()).toContain("删除这份旅行计划？");
    expect(tripApi.archive).not.toHaveBeenCalled();

    await wrapper
      .findAll("button")
      .find((button) => button.text().includes("确认删除"))!
      .trigger("click");
    await flushPromises();

    expect(tripApi.archive).toHaveBeenCalledWith("token", "trip-1", 3);
    expect(tripApi.list).toHaveBeenCalledTimes(2);
  });
});
