// 文件说明：前端功能模块：export.test。
import { describe, expect, it } from "vitest";

import { buildTripExportHtml } from "./export";
import type { PublicTrip } from "./types";

const trip: PublicTrip = {
  version: 3,
  destination: "重庆",
  origin: "上海",
  start_date: "2026-12-01",
  end_date: "2026-12-01",
  party_size: 2,
  currency: "CNY",
  generated_at: "2026-11-14T00:00:00Z",
  days: [
    {
      date: "2026-12-01",
      day_index: 1,
      theme: "初见",
      stops: [
        {
          place_id: "B001",
          place_name: "洪崖洞",
          start_at: "2026-12-01T09:00:00",
          duration_minutes: 90,
          location: null,
        },
      ],
    },
  ],
};

describe("trip export", () => {
  it("renders current version and stops without budget or owner fields", () => {
    const html = buildTripExportHtml(trip);
    expect(html).toContain("洪崖洞");
    expect(html).toContain("v3");
    expect(html).not.toContain("budget_minor");
    expect(html).not.toContain("owner_id");
  });

  it("escapes untrusted destination text", () => {
    const html = buildTripExportHtml({
      ...trip,
      destination: "<script>alert(1)</script>",
    });
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });
});
