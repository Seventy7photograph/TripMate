// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  Trip,
  TripCreateInput,
  TripUpdateInput,
  TripVersionHistory,
} from "./types";

export const tripApi = {
  list(token: string, includeArchived = false): Promise<Trip[]> {
    const query = includeArchived ? "?include_archived=true" : "";
    return request<Trip[]>(`/api/v1/trips${query}`, {}, token);
  },

  get(token: string, tripId: string): Promise<Trip> {
    return request<Trip>(
      `/api/v1/trips/${encodeURIComponent(tripId)}`,
      {},
      token,
    );
  },

  create(token: string, input: TripCreateInput): Promise<Trip> {
    return request<Trip>(
      "/api/v1/trips",
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  update(token: string, tripId: string, input: TripUpdateInput): Promise<Trip> {
    return request<Trip>(
      `/api/v1/trips/${encodeURIComponent(tripId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  archive(token: string, tripId: string, expectedVersion: number): Promise<void> {
    return request<void>(
      `/api/v1/trips/${encodeURIComponent(tripId)}?expected_version=${expectedVersion}`,
      { method: "DELETE" },
      token,
    );
  },

  versions(token: string, tripId: string): Promise<TripVersionHistory> {
    return request<TripVersionHistory>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/versions`,
      {},
      token,
    );
  },

  restoreVersion(
    token: string,
    tripId: string,
    version: number,
    expectedVersion: number,
  ): Promise<Trip> {
    return request<Trip>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/versions/${version}/restore`,
      {
        method: "POST",
        body: JSON.stringify({ expected_version: expectedVersion }),
      },
      token,
    );
  },
};
