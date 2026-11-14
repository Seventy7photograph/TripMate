// 文件说明：前端功能模块：patchApi。
import { request } from "../../lib/http";
import type { ItineraryPatch, PatchApplyResult } from "./patchTypes";

export const patchApi = {
  createReplan(
    token: string,
    tripId: string,
    input: {
      expected_version: number;
      day_id: string;
      instruction: string;
    },
  ): Promise<ItineraryPatch> {
    return request<ItineraryPatch>(
      `/api/v1/trips/${tripId}/replan`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  get(token: string, tripId: string, patchId: string): Promise<ItineraryPatch> {
    return request<ItineraryPatch>(
      `/api/v1/trips/${tripId}/patches/${patchId}`,
      {},
      token,
    );
  },

  apply(
    token: string,
    tripId: string,
    patchId: string,
    expectedVersion: number,
  ): Promise<PatchApplyResult> {
    return request<PatchApplyResult>(
      `/api/v1/trips/${tripId}/patches/${patchId}/apply`,
      {
        method: "POST",
        body: JSON.stringify({ expected_version: expectedVersion }),
      },
      token,
    );
  },

  discard(
    token: string,
    tripId: string,
    patchId: string,
    expectedVersion: number,
  ): Promise<ItineraryPatch> {
    return request<ItineraryPatch>(
      `/api/v1/trips/${tripId}/patches/${patchId}/discard`,
      {
        method: "POST",
        body: JSON.stringify({ expected_version: expectedVersion }),
      },
      token,
    );
  },
};
