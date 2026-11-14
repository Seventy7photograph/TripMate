// 文件说明：前端功能模块：form。
import type { ItineraryStop, StopLocation } from "../itinerary/types";
import type { RouteLeg, RouteLegError } from "./types";

export interface RouteSegment {
  from: ItineraryStop;
  to: ItineraryStop;
  leg: RouteLeg | null;
  error: RouteLegError | null;
  status: "available" | "missing_coordinates" | "not_calculated" | "error";
}

export function buildRouteSegments(
  stops: ItineraryStop[],
  legs: RouteLeg[],
  errors: RouteLegError[] = [],
): RouteSegment[] {
  const byPair = new Map(
    legs.map((leg) => [`${leg.from_stop_id}:${leg.to_stop_id}`, leg]),
  );
  const errorByPair = new Map(
    errors.map((error) => [`${error.from_stop_id}:${error.to_stop_id}`, error]),
  );
  return stops.slice(0, -1).map((from, index) => {
    const to = stops[index + 1]!;
    const pairKey = `${from.id}:${to.id}`;
    const leg = byPair.get(pairKey) ?? null;
    const error = errorByPair.get(pairKey) ?? null;
    const status =
      !from.location || !to.location
        ? "missing_coordinates"
        : leg
          ? "available"
          : error
            ? "error"
            : "not_calculated";
    return {
      from,
      to,
      leg,
      error,
      status,
    };
  });
}

export function createFlightArcLeg(
  from: ItineraryStop,
  to: ItineraryStop,
): RouteLeg | null {
  if (!from.location || !to.location) return null;
  const start = [from.location.longitude, from.location.latitude] as const;
  const end = [to.location.longitude, to.location.latitude] as const;
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const span = Math.hypot(dx, dy) || 1;
  const curve = Math.min(15, Math.max(1.2, span * 0.18));
  const control = [
    (start[0] + end[0]) / 2,
    Math.max(start[1], end[1]) + curve,
  ] as const;
  const points: string[] = [];
  for (let index = 0; index <= 48; index += 1) {
    const t = index / 48;
    const oneMinus = 1 - t;
    const longitude =
      oneMinus * oneMinus * start[0] +
      2 * oneMinus * t * control[0] +
      t * t * end[0];
    const latitude =
      oneMinus * oneMinus * start[1] +
      2 * oneMinus * t * control[1] +
      t * t * end[1];
    points.push(`${longitude.toFixed(6)},${latitude.toFixed(6)}`);
  }
  const distance = distanceBetweenLocations(from.location, to.location);
  return {
    id: crypto.randomUUID(),
    day_id: from.day_id,
    from_stop_id: from.id,
    to_stop_id: to.id,
    mode: "flight",
    distance_m: distance,
    duration_s: Math.max(1, Math.round(distance / 220 + 3600)),
    polyline: points.join(";"),
    provider: "schematic_arc",
    fetched_at: new Date().toISOString(),
    source: {
      provider: "schematic_arc",
      provider_place_id: null,
      source_url: null,
      queried_at: new Date().toISOString(),
      freshness: "unknown",
      confidence: 0.2,
    },
  };
}

export function distanceBetweenLocations(
  start: StopLocation,
  end: StopLocation,
): number {
  const radius = 6_371_000;
  const toRadians = Math.PI / 180;
  const lat1 = start.latitude * toRadians;
  const lat2 = end.latitude * toRadians;
  const deltaLat = (end.latitude - start.latitude) * toRadians;
  const deltaLng = (end.longitude - start.longitude) * toRadians;
  const value =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;
  return Math.round(radius * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value)));
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.max(1, Math.round(seconds / 60));
  if (totalMinutes < 60) return `${totalMinutes} 分钟`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes ? `${hours} 小时 ${minutes} 分钟` : `${hours} 小时`;
}

export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}
