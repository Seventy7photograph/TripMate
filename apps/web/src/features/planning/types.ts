// 文件说明：前端功能模块：types。
export type PlanningEventType =
  | "stage"
  | "tool_call"
  | "validation"
  | "complete"
  | "error";

export interface PlanningEvent {
  sequence: number;
  type: PlanningEventType;
  stage: string | null;
  message: string | null;
  status: string | null;
  tool_name: string | null;
  provider: string | null;
  payload: Record<string, unknown>;
}

export interface SourceMetadata {
  provider: string;
  provider_place_id: string | null;
  source_url: string | null;
  queried_at: string;
  freshness: "live" | "cached" | "mock" | "unknown";
  confidence: number;
}

export interface DraftStop {
  id: string;
  place_id: string;
  place_name: string | null;
  start_at: string;
  duration_minutes: number;
  estimated_cost_minor: number;
  source: SourceMetadata;
}

export interface DraftDay {
  id: string;
  date: string;
  theme: string | null;
  stops: DraftStop[];
  weather?: {
    status: "known" | "unknown";
    summary: string | null;
    clothing_advice: string[];
    risk: "low" | "moderate" | "high";
    evidence_ids: string[];
  };
  meals?: Array<{
    meal: "breakfast" | "lunch" | "dinner";
    status: "known" | "unknown";
    place_name: string | null;
    timing: string | null;
    opening_hours_status: "known" | "unknown";
    evidence_ids: string[];
  }>;
  transport?: Array<{
    mode: string;
    duration_minutes: number | null;
    distance_m: number | null;
    summary: string | null;
    evidence_ids: string[];
  }>;
  lodging_area?: {
    status: "known" | "unknown";
    area: string | null;
    reason: string | null;
    evidence_ids: string[];
  };
  safety?: {
    level: "low" | "moderate" | "warning" | "high";
    reminders: string[];
    disclaimer: string;
    evidence_ids: string[];
  };
  daily_summary?: string | null;
  alternatives?: string[];
  evidence_ids?: string[];
}

export interface ItineraryDraft {
  trip_id: string;
  version: number;
  days: DraftDay[];
  validation_summary: Array<{
    code: string;
    severity: string;
    path: string;
    message: string;
    repair_hint: string | null;
  }>;
}

export interface PlanningJobStart {
  job_id: string;
  status: "queued" | "running" | "completed" | "partial" | "failed";
}

export interface PlanningJob {
  id: string;
  trip_id: string | null;
  status: "queued" | "running" | "completed" | "partial" | "failed";
  progress: number;
  events: PlanningEvent[];
  result: ItineraryDraft | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  tool_call_count: number;
  loop_count: number;
}

export interface ParsedSseEvent {
  event: string;
  data: PlanningEvent;
}
