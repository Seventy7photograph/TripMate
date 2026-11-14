// 文件说明：前端功能模块：agentApi.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { travelChatApi } from "./agentApi";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("travel chat api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts message, attachments and conversation history", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        intent: "destination_research",
        in_scope: true,
        confidence: 0.9,
        answer: "泉州适合看古建。",
        sources: [],
        selected_skills: ["destination-research"],
        used_tools: ["search_places"],
        requires_planning: false,
        missing_fields: [],
        questions: [],
        model_name: "deepseek-flash",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await travelChatApi.respond(
      "token",
      "那附近还有什么？",
      ["asset-1"],
      [{ role: "user", content: "我明天去泉州。" }],
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/chat/respond",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          message: "那附近还有什么？",
          attachment_ids: ["asset-1"],
          history: [{ role: "user", content: "我明天去泉州。" }],
        }),
      }),
    );
  });
});
