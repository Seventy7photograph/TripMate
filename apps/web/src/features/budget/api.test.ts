// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { budgetApi } from "./api";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("budget API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads a trip budget", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ total_minor: 100 }));
    vi.stubGlobal("fetch", fetchMock);

    await budgetApi.get("token", "trip-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-1/budget",
      expect.any(Object),
    );
  });

  it("posts integer minor-unit expenses with expected version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ version: 4 }));
    vi.stubGlobal("fetch", fetchMock);

    await budgetApi.createExpense("token", "trip-1", {
      expected_version: 3,
      category: "food",
      amount_minor: 1230,
      currency: "CNY",
      expense_date: "2026-12-01",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-1/expenses",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expected_version: 3,
          category: "food",
          amount_minor: 1230,
          currency: "CNY",
          expense_date: "2026-12-01",
        }),
      }),
    );
  });
});
