// 文件说明：前端功能模块：types。
export interface Favorite {
  id: string;
  kind: "place" | "trip";
  target_id: string;
  label: string;
  folder: string;
  note: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ShareCreateResult {
  id: string;
  token: string;
  url_path: string;
  expires_at: string;
  created_at: string;
}

export interface ShareSummary {
  id: string;
  trip_id: string;
  status: "active" | "expired" | "revoked";
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
}

export interface PublicStop {
  place_id: string;
  place_name: string | null;
  start_at: string;
  duration_minutes: number;
  location: {
    longitude: number;
    latitude: number;
    coordinate_system: string;
  } | null;
}

export interface PublicDay {
  date: string;
  day_index: number;
  theme: string | null;
  stops: PublicStop[];
}

export interface PublicTrip {
  version: number;
  destination: string;
  origin: string | null;
  start_date: string;
  end_date: string;
  party_size: number;
  currency: string;
  days: PublicDay[];
  generated_at: string;
}

export interface TripExportDocument extends PublicTrip {
  filename: string;
}
