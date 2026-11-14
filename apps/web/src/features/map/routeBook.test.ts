// 文件说明：Web 前端测试：routeBook。
import { describe, expect, it } from "vitest";

import { selectRouteBookDay } from "./routeBook";
import type { TripDay } from "../itinerary/types";

const days: TripDay[] = [
  {
    id: "day-1",
    trip_id: "trip-1",
    date: "2026-12-01",
    day_index: 1,
    theme: "城内",
    created_at: "2026-11-15T00:00:00Z",
    updated_at: "2026-11-15T00:00:00Z",
    leg_modes: [],
    stops: [{ id: "stop-1" } as TripDay["stops"][number]],
  },
  {
    id: "day-2",
    trip_id: "trip-1",
    date: "2026-12-02",
    day_index: 2,
    theme: "近郊",
    created_at: "2026-11-15T00:00:00Z",
    updated_at: "2026-11-15T00:00:00Z",
    leg_modes: [],
    stops: [{ id: "stop-2" } as TripDay["stops"][number]],
  },
];

describe("route book selection", () => {
  it("keeps the whole trip in overview when no day is selected", () => {
    const selected = selectRouteBookDay(days, "");

    expect(selected).toBeNull();
    expect(selected?.stops ?? days.flatMap((day) => day.stops)).toHaveLength(2);
  });

  it("returns only the selected day when a day id is present", () => {
    const selected = selectRouteBookDay(days, "day-2");

    expect(selected?.id).toBe("day-2");
    expect(selected?.stops).toEqual([{ id: "stop-2" }]);
  });
});
