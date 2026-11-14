// 文件说明：前端功能模块：types。
export type RouteMode =
  | "driving"
  | "walking"
  | "bicycling"
  | "transit"
  | "bus"
  | "subway"
  | "high_speed_rail"
  | "train"
  | "flight";

export interface SourceMetadata {
  provider: string;
  provider_place_id: string | null;
  source_url: string | null;
  queried_at: string;
  freshness: "live" | "cached" | "mock" | "unknown";
  confidence: number;
}

export interface StopLocation {
  longitude: number;
  latitude: number;
  coordinate_system: "GCJ-02" | "WGS84";
}

export interface ItineraryStop {
  id: string;
  day_id: string;
  place_id: string;
  place_name: string | null;
  start_at: string;
  duration_minutes: number;
  order_index: number;
  estimated_cost_minor: number;
  location: StopLocation | null;
  source: SourceMetadata;
  created_at: string;
  updated_at: string;
}

export interface TripDay {
  id: string;
  trip_id: string;
  date: string;
  day_index: number;
  theme: string | null;
  leg_modes: RouteMode[];
  stops: ItineraryStop[];
  created_at: string;
  updated_at: string;
}

export interface Itinerary {
  trip_id: string;
  version: number;
  days: TripDay[];
}

export interface CreateDayInput {
  expected_version: number;
  date: string;
  theme?: string | null;
}

export interface CreateStopInput {
  expected_version: number;
  place_id: string;
  place_name: string | null;
  start_at: string;
  duration_minutes: number;
  estimated_cost_minor: number;
  location?: StopLocation | null;
  source?: SourceMetadata | null;
}

export interface UpdateStopInput {
  expected_version: number;
  place_id?: string;
  place_name?: string | null;
  start_at?: string;
  duration_minutes?: number;
  estimated_cost_minor?: number;
  location?: StopLocation | null;
  source?: SourceMetadata | null;
}
