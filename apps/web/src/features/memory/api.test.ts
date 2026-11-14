// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { memoryApi } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const memory = {
  id: "memory-1",
  category: "preference" as const,
  content: "住宿优先靠近地铁站",
  enabled: true,
  source: "user",
  consent_at: "2026-11-14T00:00:00Z",
  created_at: "2026-11-14T00:00:00Z",
  updated_at: "2026-11-14T00:00:00Z",
};

describe("memory API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists saved travel memories", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([memory]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(memoryApi.list("token")).resolves.toEqual([memory]);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/memories",
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );
  });

  it("creates a consented memory", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(memory, 201));
    vi.stubGlobal("fetch", fetchMock);

    await memoryApi.create("token", {
      category: "preference",
      content: memory.content,
      consent: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/memories",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          category: "preference",
          content: memory.content,
          consent: true,
        }),
      }),
    );
  });

  it("updates, deletes one, and clears all memories", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ ...memory, enabled: false }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await memoryApi.update("token", memory.id, { enabled: false });
    await memoryApi.remove("token", memory.id);
    await memoryApi.clear("token");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/memories/memory-1",
      expect.objectContaining({ method: "PATCH" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/memories/memory-1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/memories",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
