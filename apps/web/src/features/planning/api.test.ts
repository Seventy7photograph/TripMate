// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { planningApi } from "./api";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("planning API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts a planning job with the trip version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ job_id: "job-1", status: "completed" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await planningApi.start("token", "trip-1", 3);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-1/plan",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_version: 3 }),
      }),
    );
  });

  it("can request applying the generated draft to the itinerary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ job_id: "job-1", status: "completed" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await planningApi.start("token", "trip-1", 3, true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-1/plan",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expected_version: 3,
          apply_to_itinerary: true,
        }),
      }),
    );
  });

  it("polls a planning job", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: "job-1", status: "completed" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await planningApi.get("token", "job-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/jobs/job-1",
      expect.any(Object),
    );
  });
});
