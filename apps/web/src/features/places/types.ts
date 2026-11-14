// 文件说明：前端功能模块：types。
export type CoordinateSystem = "GCJ-02" | "WGS84";
export type SourceFreshness = "live" | "cached" | "mock" | "unknown";

export interface PlaceLocation {
  longitude: number;
  latitude: number;
  coordinate_system: CoordinateSystem;
}

export interface PlaceSource {
  provider: string;
  provider_place_id: string | null;
  source_url: string | null;
  queried_at: string;
  freshness: SourceFreshness;
  confidence: number;
}

export interface Place {
  provider_place_id: string;
  name: string;
  category: string | null;
  address: string | null;
  location: PlaceLocation | null;
  tel: string | null;
  opening_hours: string[];
  source: PlaceSource;
}

export interface PlaceSearchResponse {
  provider: string;
  profile: "mock" | "live";
  cached: boolean;
  results: Place[];
}

export interface ProviderStatus {
  profile: "mock" | "live";
  provider: string;
  configured: boolean;
  capabilities: string[];
}

export interface GeocodeResult {
  longitude: number;
  latitude: number;
  coordinate_system: CoordinateSystem;
}
