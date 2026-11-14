// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { conversationApi } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("conversation api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates and then patches a persisted conversation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          id: "conversation-1",
          title: "重庆",
          messages: [],
          requirement_history: [],
          trip_id: null,
          version: 1,
          message_count: 0,
          created_at: "2026-11-14T00:00:00Z",
          updated_at: "2026-11-14T00:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: "conversation-1",
          title: "重庆",
          messages: [],
          requirement_history: ["继续"],
          trip_id: null,
          version: 2,
          message_count: 0,
          created_at: "2026-11-14T00:00:00Z",
          updated_at: "2026-11-14T00:01:00Z",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await conversationApi.create("token", {
      title: "重庆",
      messages: [],
      requirement_history: [],
    });
    await conversationApi.update("token", "conversation-1", 1, {
      title: "重庆",
      messages: [],
      requirement_history: ["继续"],
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/conversations",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/conversations/conversation-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          expected_version: 1,
          title: "重庆",
          messages: [],
          requirement_history: ["继续"],
        }),
      }),
    );
  });
});
