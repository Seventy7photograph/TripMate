// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import { parseSseBlock } from "./sse";
import type {
  ParsedSseEvent,
  PlanningJob,
  PlanningJobStart,
} from "./types";

export const planningApi = {
  start(
    token: string,
    tripId: string,
    expectedVersion: number,
    applyToItinerary = false,
  ): Promise<PlanningJobStart> {
    return request<PlanningJobStart>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/plan`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_version: expectedVersion,
          ...(applyToItinerary ? { apply_to_itinerary: true } : {}),
        }),
      },
      token,
    );
  },

  get(token: string, jobId: string): Promise<PlanningJob> {
    return request<PlanningJob>(
      `/api/v1/jobs/${encodeURIComponent(jobId)}`,
      {},
      token,
    );
  },

  async streamEvents(
    token: string,
    jobId: string,
    onEvent: (event: ParsedSseEvent) => void,
  ): Promise<void> {
    const response = await fetch(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/events`,
      {
        headers: {
          Accept: "text/event-stream",
          Authorization: `Bearer ${token}`,
        },
      },
    );
    if (!response.ok) {
      throw new Error("SSE connection failed");
    }
    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separator = buffer.search(/\r?\n\r?\n/);
      while (separator >= 0) {
        const block = buffer.slice(0, separator);
        buffer = buffer.slice(separator + (buffer[separator] === "\r" ? 4 : 2));
        const event = parseSseBlock(block);
        if (event) onEvent(event);
        separator = buffer.search(/\r?\n\r?\n/);
      }
    }
  },
};
