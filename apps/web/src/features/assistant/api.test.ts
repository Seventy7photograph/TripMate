// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { assistantApi } from "./api";
import type { RequirementParseResult } from "./types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const parsed: RequirementParseResult = {
  brief: {
    destination: "重庆",
    origin: "上海",
    start_date: "2026-12-01",
    end_date: "2026-12-03",
    party_size: 2,
    budget_minor: 500_000,
    currency: "CNY",
    interests: ["美食"],
    pace: "relaxed",
    transport_preferences: [],
    transport_strategy: {
      strategy: "unspecified",
      segments: [],
      constraints: [],
    },
    lodging_preferences: [],
    must_visit: [],
    avoid: [],
    constraints: [],
  },
  draft: {
    destination: "重庆",
    origin: "上海",
    start_date: "2026-12-01",
    end_date: "2026-12-03",
    party_size: 2,
    budget_minor: 500_000,
    currency: "CNY",
    interests: ["美食"],
    pace: "relaxed",
  },
  missing_fields: [],
  questions: [],
};

describe("assistant API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses natural-language requirements with the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(parsed));
    vi.stubGlobal("fetch", fetchMock);

    const result = await assistantApi.parse(
      "token",
      "2人去重庆，预算5000元",
      ["asset-1"],
    );

    expect(result).toEqual(parsed);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/briefs/parse",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          text: "2人去重庆，预算5000元",
          attachment_ids: ["asset-1"],
        }),
        headers: expect.any(Headers),
      }),
    );
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((options.headers as Headers).get("Authorization")).toBe("Bearer token");
  });
});
