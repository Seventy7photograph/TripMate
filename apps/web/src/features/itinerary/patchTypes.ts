// 文件说明：前端功能模块：patchTypes。
import type { Itinerary } from "./types";

export interface PatchChange {
  target_day_date: string;
  removed_stop_ids: string[];
  added_stop_ids: string[];
  before_stops: Array<{
    id: string;
    place_id: string;
    place_name: string | null;
    start_at: string;
    duration_minutes: number;
    order_index: number;
  }>;
  after_stops: PatchChange["before_stops"];
  before_stop_count: number;
  after_stop_count: number;
}

export interface ItineraryPatch {
  id: string;
  trip_id: string;
  target_day_id: string;
  base_version: number;
  applied_version: number | null;
  status: "pending" | "applied" | "discarded";
  instruction: string;
  changes: PatchChange;
  created_at: string;
  applied_at: string | null;
}

export interface PatchApplyResult extends ItineraryPatch {
  itinerary: Itinerary;
}
