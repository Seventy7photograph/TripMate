// 文件说明：前端功能模块：form.test。
import { describe, expect, it } from "vitest";

import {
  dateTimeFor,
  datesBetween,
  parseAmountToMinor,
  timeFromDateTime,
} from "./form";

describe("itinerary form helpers", () => {
  it("combines a trip day and local time without changing the date", () => {
    expect(dateTimeFor("2026-12-01", "09:30")).toBe("2026-12-01T09:30:00");
    expect(dateTimeFor("2026-12-01", "23:59")).toBe("2026-12-01T23:59:00");
  });

  it("extracts a stable local time for editing", () => {
    expect(timeFromDateTime("2026-12-01T09:30:00")).toBe("09:30");
    expect(timeFromDateTime("2026-12-01T09:30:00+08:00")).toBe("09:30");
  });

  it("converts spend amounts to integer minor units", () => {
    expect(parseAmountToMinor("")).toBeNull();
    expect(parseAmountToMinor("32.5")).toBe(3250);
    expect(parseAmountToMinor("0")).toBe(0);
    expect(parseAmountToMinor("12.345")).toBeUndefined();
  });

  it("builds every calendar day in an inclusive trip range", () => {
    expect(datesBetween("2026-12-01", "2026-12-03")).toEqual([
      "2026-12-01",
      "2026-12-02",
      "2026-12-03",
    ]);
    expect(datesBetween("2026-12-03", "2026-12-01")).toEqual([]);
  });
});
