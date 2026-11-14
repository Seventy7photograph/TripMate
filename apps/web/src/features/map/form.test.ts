// 文件说明：前端功能模块：form.test。
import { describe, expect, it } from "vitest";

import type { ItineraryStop } from "../itinerary/types";
import {
  buildRouteSegments,
  createFlightArcLeg,
  formatDistance,
  formatDuration,
} from "./form";
import type { RouteLeg } from "./types";

function stop(id: string, withLocation: boolean): ItineraryStop {
  return {
    id,
    day_id: "day-1",
    place_id: `manual-${id}`,
    place_name: id,
    start_at: "2026-12-01T09:00:00",
    duration_minutes: 60,
    order_index: 0,
    estimated_cost_minor: 0,
    location: withLocation
      ? { longitude: 106.5, latitude: 29.5, coordinate_system: "GCJ-02" }
      : null,
    source: {
      provider: "mock",
      provider_place_id: null,
      source_url: null,
      queried_at: "2026-11-13T12:00:00Z",
      freshness: "mock",
      confidence: 1,
    },
    created_at: "2026-11-13T12:00:00Z",
    updated_at: "2026-11-13T12:00:00Z",
  };
}

function leg(from: string, to: string): RouteLeg {
  return {
    id: `${from}-${to}`,
    day_id: "day-1",
    from_stop_id: from,
    to_stop_id: to,
    mode: "walking",
    distance_m: 1200,
    duration_s: 900,
    polyline: null,
    provider: "mock",
    fetched_at: "2026-11-13T12:00:00Z",
    source: {
      provider: "mock",
      provider_place_id: null,
      source_url: null,
      queried_at: "2026-11-13T12:00:00Z",
      freshness: "mock",
      confidence: 1,
    },
  };
}

describe("map route helpers", () => {
  it("marks segments without coordinates and never invents a leg", () => {
    const stops = [stop("a", true), stop("b", false), stop("c", true)];
    const segments = buildRouteSegments(stops, [leg("a", "c")]);

    expect(segments).toHaveLength(2);
    expect(segments[0]?.status).toBe("missing_coordinates");
    expect(segments[0]?.leg).toBeNull();
    expect(segments[1]?.status).toBe("missing_coordinates");
    expect(segments[1]?.leg).toBeNull();
  });

  it("does not confuse an uncalculated route with missing coordinates", () => {
    const segments = buildRouteSegments([stop("a", true), stop("c", true)], []);

    expect(segments[0]?.status).toBe("not_calculated");
    expect(segments[0]?.leg).toBeNull();
  });

  it("keeps a failed mixed-mode segment as an explicit error", () => {
    const segments = buildRouteSegments(
      [stop("a", true), stop("b", true)],
      [],
      [
        {
          from_stop_id: "a",
          to_stop_id: "b",
          mode: "walking",
          code: "provider_response_invalid",
          message: "步行距离超过限制",
        },
      ],
    );

    expect(segments[0]?.status).toBe("error");
    expect(segments[0]?.error?.message).toBe("步行距离超过限制");
  });

  it("creates a visible schematic arc for flight", () => {
    const from = stop("a", true);
    const to = stop("b", true);
    to.location = {
      longitude: 87.6168,
      latitude: 43.8256,
      coordinate_system: "GCJ-02",
    };

    const flight = createFlightArcLeg(from, to);

    expect(flight?.mode).toBe("flight");
    expect(flight?.provider).toBe("schematic_arc");
    expect(flight?.polyline?.split(";")).toHaveLength(49);
    expect(flight?.distance_m).toBeGreaterThan(1_000_000);
    const points = (flight?.polyline ?? "").split(";").map((point) =>
      point.split(",").map(Number),
    );
    const midpointLatitude = points[24]?.[1] ?? 0;
    expect(midpointLatitude).toBeGreaterThan(
      (from.location!.latitude + to.location!.latitude) / 2,
    );
  });

  it("formats route distance and duration", () => {
    expect(formatDistance(850)).toBe("850 m");
    expect(formatDistance(4400)).toBe("4.4 km");
    expect(formatDuration(1968)).toBe("33 分钟");
    expect(formatDuration(5400)).toBe("1 小时 30 分钟");
  });
});
