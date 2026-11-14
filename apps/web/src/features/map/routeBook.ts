// 文件说明：Web 前端模块：路书选择状态。
import type { TripDay } from "../itinerary/types";

export function selectRouteBookDay(
  days: TripDay[],
  dayId: string,
): TripDay | null {
  if (!dayId) return null;
  return days.find((day) => day.id === dayId) ?? null;
}
