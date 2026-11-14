// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { favoriteApi, shareApi } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("share and favorite api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses scoped favorite and share endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([], 200))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: "share-1",
            token: "public-token",
            url_path: "/share/public-token",
            expires_at: "2026-12-14T00:00:00Z",
            created_at: "2026-11-14T00:00:00Z",
          },
          201,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ destination: "重庆", days: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await favoriteApi.list("token", "place");
    await shareApi.create("token", "trip-1", 30);
    await shareApi.publicTrip("public-token");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/favorites?kind=place",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/trips/trip-1/shares",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/public/trips/public-token",
      expect.any(Object),
    );
  });

  it("updates favorite folder and note", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: "favorite-1",
        kind: "place",
        target_id: "B001",
        label: "洪崖洞",
        folder: "夜景收藏",
        note: "下次带相机",
        details: {},
        created_at: "2026-11-14T00:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await favoriteApi.update("token", "favorite-1", {
      folder: "夜景收藏",
      note: "下次带相机",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/favorites/favorite-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          folder: "夜景收藏",
          note: "下次带相机",
        }),
      }),
    );
  });
});
