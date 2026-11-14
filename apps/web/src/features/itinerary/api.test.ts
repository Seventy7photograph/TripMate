// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { itineraryApi } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("itinerary API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the full itinerary for a trip", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        trip_id: "trip-id",
        version: 1,
        days: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const itinerary = await itineraryApi.get("token", "trip-id");

    expect(itinerary.days).toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-id/itinerary",
      expect.any(Object),
    );
  });

  it("sends the complete stop order when reordering", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: "day-id", stops: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await itineraryApi.reorderStops(
      "token",
      "day-id",
      ["stop-b", "stop-a"],
      4,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/days/day-id/stops/reorder",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          stop_ids: ["stop-b", "stop-a"],
          expected_version: 4,
        }),
      }),
    );
  });

  it("deletes a stop and accepts an empty 204 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await itineraryApi.deleteStop("token", "stop-id", 5);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/stops/stop-id?expected_version=5",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
