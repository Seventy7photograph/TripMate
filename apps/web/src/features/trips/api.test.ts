// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { tripApi } from "./api";
import type { TripBriefInput } from "./form";

const brief: TripBriefInput = {
  destination: "Chongqing",
  origin: "Shanghai",
  start_date: "2026-12-01",
  end_date: "2026-12-03",
  party_size: 2,
  budget_minor: 500_000,
  currency: "CNY",
  interests: ["food"],
  pace: "balanced",
  transport_preferences: ["public_transit"],
  lodging_preferences: [],
  must_visit: [],
  avoid: [],
  constraints: [],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("trip API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a trip with the current bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: "trip-id",
        owner_id: "owner-id",
        status: "draft",
        version: 1,
        brief,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const trip = await tripApi.create("token", { brief });

    expect(trip.id).toBe("trip-id");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ brief }),
        headers: expect.any(Headers),
      }),
    );
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((options.headers as Headers).get("Authorization")).toBe("Bearer token");
  });

  it("requests archived trips only when asked", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await tripApi.list("token", true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips?include_archived=true",
      expect.any(Object),
    );
  });

  it("archives a trip with DELETE", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await tripApi.archive("token", "trip-id", 3);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-id?expected_version=3",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
