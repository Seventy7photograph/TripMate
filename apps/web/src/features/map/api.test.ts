// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { routeApi } from "./api";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("route API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts complete stop order, modes and expected version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await routeApi.calculate("token", "trip-1", "day-1", {
      expected_version: 7,
      stop_ids: ["a", "b"],
      mode: "driving",
      modes: ["walking"],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-1/days/day-1/routes",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expected_version: 7,
          stop_ids: ["a", "b"],
          mode: "driving",
          modes: ["walking"],
        }),
      }),
    );
  });

  it("builds an authenticated static map image URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("<svg>map</svg>", {
        status: 200,
        headers: {
          "Content-Type": "image/svg+xml",
          "X-Route-Available": "true",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const image = await routeApi.mapImage("token", "trip-1", "day-1", {
      expected_version: 8,
      mode: "walking",
      zoom: 14,
      include_route: true,
    });

    expect(image.routeAvailable).toBe(true);
    expect(image.blob.type).toBe("image/svg+xml");
    expect(fetchMock.mock.calls[0]?.[0]).toContain(
      "/api/v1/trips/trip-1/days/day-1/map?",
    );
  });
});
