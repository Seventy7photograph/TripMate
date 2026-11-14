// 文件说明：前端功能模块：types。
import type { RouteMode, SourceMetadata } from "../itinerary/types";

export interface RouteLeg {
  id: string;
  day_id: string;
  from_stop_id: string;
  to_stop_id: string;
  mode: RouteMode;
  distance_m: number;
  duration_s: number;
  polyline: string | null;
  provider: string;
  fetched_at: string;
  source: SourceMetadata;
}

export interface RouteLegError {
  from_stop_id: string;
  to_stop_id: string;
  mode: RouteMode;
  code: string;
  message: string;
}

export interface RouteCalculationResult {
  legs: RouteLeg[];
  errors: RouteLegError[];
  modes: RouteMode[];
}

export interface RouteCalculateInput {
  expected_version: number;
  stop_ids: string[];
  mode: RouteMode;
  modes?: RouteMode[];
}

export interface MapImageResult {
  blob: Blob;
  routeAvailable: boolean;
  mediaType: string;
}
