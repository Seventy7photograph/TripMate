// 文件说明：前端功能模块：types。
export type MemoryCategory =
  | "preference"
  | "food"
  | "mobility"
  | "lodging"
  | "budget"
  | "avoid"
  | "other";

export interface TravelMemory {
  id: string;
  category: MemoryCategory;
  content: string;
  enabled: boolean;
  source: string;
  consent_at: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryCreateInput {
  category: MemoryCategory;
  content: string;
  consent: boolean;
}

export interface MemoryUpdateInput {
  category?: MemoryCategory;
  content?: string;
  enabled?: boolean;
}
