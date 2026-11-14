// 文件说明：前端功能模块：patchApi.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { patchApi } from "./patchApi";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const patch = {
  id: "patch-1",
  trip_id: "trip-1",
  target_day_id: "day-1",
  base_version: 3,
  applied_version: null,
  status: "pending",
  instruction: "减少一个景点",
  changes: {
    target_day_date: "2026-12-01",
    removed_stop_ids: ["stop-2"],
    added_stop_ids: [],
    before_stops: [],
    after_stops: [],
    before_stop_count: 2,
    after_stop_count: 1,
  },
  created_at: "2026-11-14T00:00:00Z",
  applied_at: null,
};

describe("patch api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates, applies and discards only through explicit actions", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(patch, 201))
      .mockResolvedValueOnce(jsonResponse({ ...patch, status: "applied" }))
      .mockResolvedValueOnce(jsonResponse({ ...patch, status: "discarded" }));
    vi.stubGlobal("fetch", fetchMock);

    await patchApi.createReplan("token", "trip-1", {
      expected_version: 3,
      day_id: "day-1",
      instruction: "减少一个景点",
    });
    await patchApi.apply("token", "trip-1", "patch-1", 3);
    await patchApi.discard("token", "trip-1", "patch-1", 3);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/trips/trip-1/replan",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/trips/trip-1/patches/patch-1/apply",
      expect.objectContaining({
        body: JSON.stringify({ expected_version: 3 }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/trips/trip-1/patches/patch-1/discard",
      expect.objectContaining({
        body: JSON.stringify({ expected_version: 3 }),
      }),
    );
  });
});
