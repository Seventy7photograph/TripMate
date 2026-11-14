// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  Favorite,
  PublicTrip,
  ShareCreateResult,
  ShareSummary,
  TripExportDocument,
} from "./types";

export const favoriteApi = {
  list(
    token: string,
    kind?: "place" | "trip",
    folder?: string,
  ): Promise<Favorite[]> {
    const params = new URLSearchParams();
    if (kind) params.set("kind", kind);
    if (folder) params.set("folder", folder);
    const query = params.size ? `?${params.toString()}` : "";
    return request<Favorite[]>(`/api/v1/favorites${query}`, {}, token);
  },

  create(
    token: string,
    input: {
      kind: "place" | "trip";
      target_id: string;
      label: string;
      folder?: string;
      note?: string | null;
      details?: Record<string, unknown>;
    },
  ): Promise<Favorite> {
    return request<Favorite>(
      "/api/v1/favorites",
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  update(
    token: string,
    favoriteId: string,
    input: { folder?: string; note?: string | null },
  ): Promise<Favorite> {
    return request<Favorite>(
      `/api/v1/favorites/${encodeURIComponent(favoriteId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  remove(token: string, favoriteId: string): Promise<void> {
    return request<void>(
      `/api/v1/favorites/${encodeURIComponent(favoriteId)}`,
      { method: "DELETE" },
      token,
    );
  },
};

export const shareApi = {
  create(
    token: string,
    tripId: string,
    expiresInDays = 30,
  ): Promise<ShareCreateResult> {
    return request<ShareCreateResult>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/shares`,
      {
        method: "POST",
        body: JSON.stringify({ expires_in_days: expiresInDays }),
      },
      token,
    );
  },

  list(token: string, tripId: string): Promise<ShareSummary[]> {
    return request<ShareSummary[]>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/shares`,
      {},
      token,
    );
  },

  revoke(token: string, shareId: string): Promise<void> {
    return request<void>(
      `/api/v1/shares/${encodeURIComponent(shareId)}`,
      { method: "DELETE" },
      token,
    );
  },

  publicTrip(token: string): Promise<PublicTrip> {
    return request<PublicTrip>(
      `/api/v1/public/trips/${encodeURIComponent(token)}`,
    );
  },

  exportDocument(token: string, tripId: string): Promise<TripExportDocument> {
    return request<TripExportDocument>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/export`,
      {},
      token,
    );
  },
};
