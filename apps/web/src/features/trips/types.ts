// 文件说明：前端功能模块：types。
export type TripStatus = "draft" | "planning" | "ready" | "archived";
export type TripPace = "relaxed" | "balanced" | "intensive";
export type TransportMode =
  | "self_drive"
  | "rental_car"
  | "taxi"
  | "public_transit"
  | "walking"
  | "cycling"
  | "high_speed_rail"
  | "train"
  | "flight"
  | "ferry"
  | "chartered_car"
  | "mixed";
export type TransportCoverage =
  | "whole_trip"
  | "intercity"
  | "destination_local"
  | "specific_days"
  | "partial";

export interface TransportSegmentPreference {
  mode: TransportMode;
  coverage: TransportCoverage;
  days: number[] | null;
  parking_required: boolean | null;
  description: string;
}

export interface TransportStrategy {
  strategy: "single" | "mixed" | "unspecified";
  segments: TransportSegmentPreference[];
  constraints: string[];
}

export interface TripBrief {
  destination: string;
  origin: string | null;
  start_date: string;
  end_date: string;
  party_size: number;
  budget_minor: number | null;
  currency: string;
  interests: string[];
  pace: TripPace;
  transport_preferences: string[];
  transport_strategy: TransportStrategy;
  lodging_preferences: string[];
  must_visit: string[];
  avoid: string[];
  constraints: string[];
}

export interface Trip {
  id: string;
  owner_id: string;
  status: TripStatus;
  version: number;
  brief: TripBrief;
  created_at: string;
  updated_at: string;
}

export interface TripCreateInput {
  brief: TripBrief;
}

export interface TripUpdateInput {
  expected_version: number;
  brief?: TripBrief;
  status?: TripStatus;
}

export interface TripVersion {
  version: number;
  snapshot: {
    trip: {
      status: TripStatus;
      version: number;
      brief: TripBrief;
      [key: string]: unknown;
    };
    days: unknown[];
    [key: string]: unknown;
  };
  created_by: string;
  created_at: string;
}

export interface TripVersionHistory {
  trip_id: string;
  current_version: number;
  versions: TripVersion[];
}
