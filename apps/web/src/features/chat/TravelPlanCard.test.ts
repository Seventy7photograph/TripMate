// 文件说明：Web 前端测试：TravelPlanCard。
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TravelPlanCard from "./TravelPlanCard.vue";
import type { ItineraryDraft } from "../planning/types";
import type { Trip } from "../trips/types";

const brief = {
  destination: "泉州",
  origin: "上海",
  start_date: "2026-12-20",
  end_date: "2026-12-21",
  party_size: 2,
  budget_minor: 300_000,
  currency: "CNY",
  interests: ["古建"],
  pace: "balanced" as const,
  transport_preferences: [],
  lodging_preferences: [],
  must_visit: [],
  avoid: [],
  constraints: [],
};

const trip: Trip = {
  id: "trip-1",
  owner_id: "user-1",
  status: "draft",
  version: 1,
  brief,
  created_at: "2026-11-15T00:00:00Z",
  updated_at: "2026-11-15T00:00:00Z",
};

const itinerary: ItineraryDraft = {
  trip_id: "trip-1",
  version: 1,
  validation_summary: [],
  days: [
    {
      id: "day-1",
      date: "2026-12-20",
      theme: "古城",
      stops: [],
      evidence_ids: ["ev-weather", "ev-food"],
      daily_summary: "上午古城，下午留出休息时间。",
      alternatives: ["雨天改为博物馆"],
      weather: {
        status: "known",
        summary: "晴，22/11°C",
        clothing_advice: ["早晚加外套"],
        risk: "low",
        evidence_ids: ["ev-weather"],
      },
      meals: [
        {
          meal: "lunch",
          status: "known",
          place_name: "西街小吃",
          timing: "12:00",
          opening_hours_status: "known",
          evidence_ids: ["ev-food"],
        },
      ],
      transport: [],
      lodging_area: {
        status: "known",
        area: "钟楼地铁站周边",
        reason: "交通方便",
        evidence_ids: ["ev-lodging"],
      },
      safety: {
        level: "low",
        reminders: ["保管随身物品"],
        disclaimer: "不替代医疗意见",
        evidence_ids: ["ev-safety"],
      },
    },
  ],
};

describe("TravelPlanCard rich facts", () => {
  it("renders weather, meals, lodging, safety, summary and alternatives", () => {
    const wrapper = mount(TravelPlanCard, {
      props: { trip, itinerary },
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    expect(wrapper.text()).toContain("晴，22/11°C");
    expect(wrapper.text()).toContain("西街小吃");
    expect(wrapper.text()).toContain("钟楼地铁站周边");
    expect(wrapper.text()).toContain("保管随身物品");
    expect(wrapper.text()).toContain("上午古城");
    expect(wrapper.text()).toContain("雨天改为博物馆");
  });
});
