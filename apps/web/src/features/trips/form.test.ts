// 文件说明：前端功能模块：form.test。
import { describe, expect, it } from "vitest";

import {
  parseYuanToMinor,
  splitList,
  toTripBriefInput,
  validateTripBriefForm,
  type TripBriefFormInput,
} from "./form";

function form(overrides: Partial<TripBriefFormInput> = {}): TripBriefFormInput {
  return {
    destination: "Chongqing",
    origin: "Shanghai",
    startDate: "2026-12-01",
    endDate: "2026-12-03",
    partySize: "2",
    budgetAmount: "5000.25",
    currency: "CNY",
    interests: "food, citywalk",
    pace: "balanced",
    transportPreferences: "public_transit",
    transportStrategy: {
      strategy: "unspecified",
      segments: [],
      constraints: [],
    },
    lodgingPreferences: "central",
    mustVisit: "Hongya Cave",
    avoid: "crowded",
    constraints: "no spicy food",
    ...overrides,
  };
}

describe("trip brief form", () => {
  it("converts yuan to integer minor units without floating point math", () => {
    expect(parseYuanToMinor("")).toBeNull();
    expect(parseYuanToMinor("0")).toBe(0);
    expect(parseYuanToMinor("5000.25")).toBe(500_025);
    expect(parseYuanToMinor("5000.2")).toBe(500_020);
    expect(parseYuanToMinor("5000.255")).toBeUndefined();
  });

  it("normalizes comma and newline separated preferences", () => {
    expect(splitList(" food, citywalk\nmuseum ,, ")).toEqual([
      "food",
      "citywalk",
      "museum",
    ]);
  });

  it("maps the form to the shared TripBrief contract", () => {
    expect(toTripBriefInput(form())).toMatchObject({
      destination: "Chongqing",
      origin: "Shanghai",
      start_date: "2026-12-01",
      end_date: "2026-12-03",
      party_size: 2,
      budget_minor: 500_025,
      currency: "CNY",
      interests: ["food", "citywalk"],
      pace: "balanced",
      transport_preferences: ["public_transit"],
      transport_strategy: {
        strategy: "unspecified",
        segments: [],
        constraints: [],
      },
    });
  });

  it("rejects reversed dates and invalid amounts", () => {
    expect(
      validateTripBriefForm(form({ startDate: "2026-12-05" })),
    ).toBe("开始日期不能晚于结束日期。");
    expect(
      validateTripBriefForm(form({ budgetAmount: "12.345" })),
    ).toBe("预算最多保留两位小数。");
  });
});
