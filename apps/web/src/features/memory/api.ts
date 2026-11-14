// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  MemoryCreateInput,
  MemoryUpdateInput,
  TravelMemory,
} from "./types";

export const memoryApi = {
  list(token: string): Promise<TravelMemory[]> {
    return request<TravelMemory[]>("/api/v1/memories", {}, token);
  },

  create(token: string, input: MemoryCreateInput): Promise<TravelMemory> {
    return request<TravelMemory>(
      "/api/v1/memories",
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  update(
    token: string,
    memoryId: string,
    input: MemoryUpdateInput,
  ): Promise<TravelMemory> {
    return request<TravelMemory>(
      `/api/v1/memories/${encodeURIComponent(memoryId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
      token,
    );
  },

  remove(token: string, memoryId: string): Promise<void> {
    return request<void>(
      `/api/v1/memories/${encodeURIComponent(memoryId)}`,
      { method: "DELETE" },
      token,
    );
  },

  clear(token: string): Promise<void> {
    return request<void>("/api/v1/memories", { method: "DELETE" }, token);
  },
};
