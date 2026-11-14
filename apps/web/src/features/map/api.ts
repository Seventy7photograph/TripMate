// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type { RouteMode } from "../itinerary/types";
import type {
  MapImageResult,
  RouteCalculationResult,
  RouteCalculateInput,
} from "./types";

export const routeApi = {
  calculate(
    token: string,
    tripId: string,
    dayId: string,
    input: RouteCalculateInput,
  ): Promise<RouteCalculationResult> {
    return request<RouteCalculationResult>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/days/${encodeURIComponent(dayId)}/routes`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  async mapImage(
    token: string,
    tripId: string,
    dayId: string,
    input: {
      expected_version: number;
      mode: RouteMode;
      zoom: number;
      include_route: boolean;
    },
  ): Promise<MapImageResult> {
    const params = new URLSearchParams({
      expected_version: String(input.expected_version),
      mode: input.mode,
      zoom: String(input.zoom),
      include_route: String(input.include_route),
    });
    const response = await fetch(
      `/api/v1/trips/${encodeURIComponent(tripId)}/days/${encodeURIComponent(dayId)}/map?${params.toString()}`,
      {
        headers: {
          Accept: "image/*",
          Authorization: `Bearer ${token}`,
        },
      },
    );
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null);
      const detail =
        typeof payload === "object" &&
        payload !== null &&
        "detail" in payload &&
        typeof payload.detail === "object" &&
        payload.detail !== null &&
        "message" in payload.detail
          ? String(payload.detail.message)
          : "Map request failed";
      throw new Error(detail);
    }
    return {
      blob: await response.blob(),
      routeAvailable: response.headers.get("X-Route-Available") === "true",
      mediaType: response.headers.get("Content-Type") ?? "image/png",
    };
  },
};
