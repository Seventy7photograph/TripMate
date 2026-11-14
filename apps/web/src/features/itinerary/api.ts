// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  CreateDayInput,
  CreateStopInput,
  Itinerary,
  ItineraryStop,
  TripDay,
  UpdateStopInput,
} from "./types";

export const itineraryApi = {
  get(token: string, tripId: string): Promise<Itinerary> {
    return request<Itinerary>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/itinerary`,
      {},
      token,
    );
  },

  createDay(token: string, tripId: string, input: CreateDayInput): Promise<TripDay> {
    return request<TripDay>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/days`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  createStop(token: string, dayId: string, input: CreateStopInput): Promise<ItineraryStop> {
    return request<ItineraryStop>(
      `/api/v1/days/${encodeURIComponent(dayId)}/stops`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  updateStop(
    token: string,
    stopId: string,
    input: UpdateStopInput,
  ): Promise<ItineraryStop> {
    return request<ItineraryStop>(
      `/api/v1/stops/${encodeURIComponent(stopId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  deleteStop(token: string, stopId: string, expectedVersion: number): Promise<void> {
    return request<void>(
      `/api/v1/stops/${encodeURIComponent(stopId)}?expected_version=${expectedVersion}`,
      { method: "DELETE" },
      token,
    );
  },

  reorderStops(
    token: string,
    dayId: string,
    stopIds: string[],
    expectedVersion: number,
  ): Promise<TripDay> {
    return request<TripDay>(
      `/api/v1/days/${encodeURIComponent(dayId)}/stops/reorder`,
      {
        method: "PUT",
        body: JSON.stringify({
          stop_ids: stopIds,
          expected_version: expectedVersion,
        }),
      },
      token,
    );
  },
};
