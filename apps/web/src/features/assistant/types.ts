// 文件说明：前端功能模块：types。
import type { TripBrief } from "../trips/types";

export type TripBriefDraft = Partial<TripBrief>;

export interface RequirementParseResult {
  brief: TripBrief | null;
  draft: TripBriefDraft;
  missing_fields: string[];
  questions: string[];
}
