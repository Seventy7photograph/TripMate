// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  GeocodeResult,
  Place,
  PlaceSearchResponse,
  ProviderStatus,
} from "./types";

export const placeApi = {
  status(token: string): Promise<ProviderStatus> {
    return request<ProviderStatus>("/api/v1/providers/map/status", {}, token);
  },

  search(
    token: string,
    input: { query: string; city?: string; limit?: number },
  ): Promise<PlaceSearchResponse> {
    const params = new URLSearchParams({ q: input.query });
    if (input.city) params.set("city", input.city);
    if (input.limit) params.set("limit", String(input.limit));
    return request<PlaceSearchResponse>(
      `/api/v1/places/search?${params.toString()}`,
      {},
      token,
    );
  },

  get(token: string, providerPlaceId: string): Promise<Place> {
    return request<Place>(
      `/api/v1/places/${encodeURIComponent(providerPlaceId)}`,
      {},
      token,
    );
  },

  geocode(token: string, address: string): Promise<GeocodeResult> {
    const params = new URLSearchParams({ address });
    return request<GeocodeResult>(
      `/api/v1/places/geocode?${params.toString()}`,
      {},
      token,
    );
  },
};
