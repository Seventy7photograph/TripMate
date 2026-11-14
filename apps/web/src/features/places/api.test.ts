// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { placeApi } from "./api";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("place API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("encodes query, city and limit for search", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        provider: "mock",
        profile: "mock",
        results: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await placeApi.search("token", { query: "洪崖洞", city: "重庆", limit: 8 });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/places/search?q=%E6%B4%AA%E5%B4%96%E6%B4%9E&city=%E9%87%8D%E5%BA%86&limit=8",
      expect.any(Object),
    );
  });

  it("loads provider status and place detail", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          provider: "mock",
          profile: "mock",
          capabilities: ["search", "detail"],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ provider_place_id: "mock-1" }));
    vi.stubGlobal("fetch", fetchMock);

    await placeApi.status("token");
    await placeApi.get("token", "mock-1");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/providers/map/status");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/places/mock-1");
  });
});
