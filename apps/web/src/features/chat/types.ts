// 文件说明：前端功能模块：types。
import type { ItineraryDraft, PlanningJob } from "../planning/types";
import type {
  TransportStrategy,
  Trip,
  TripBrief,
} from "../trips/types";
import type { UploadedAsset } from "../upload/types";

export type ConversationMessageKind =
  | "text"
  | "questions"
  | "working"
  | "plan"
  | "answer";

export type TravelIntent =
  | "plan_trip"
  | "travel_question"
  | "destination_research"
  | "route_advice"
  | "budget_advice"
  | "clarify"
  | "out_of_scope";

export interface ChatSourceCitation {
  url: string;
  title?: string | null;
  cited_text?: string | null;
  published_at?: string | null;
}

export interface TravelChatHistoryTurn {
  role: "assistant" | "user";
  content: string;
}

export interface TravelChatResponse {
  intent: TravelIntent;
  in_scope: boolean;
  confidence: number;
  answer?: string | null;
  sources: ChatSourceCitation[];
  selected_skills: string[];
  used_tools: string[];
  skill_failures?: Array<{ name: string; error: string }>;
  requires_planning: boolean;
  brief?: TripBrief | null;
  draft?: PlanningDraft | null;
  missing_fields: string[];
  questions: string[];
  model_name: string;
}

export interface PlanningDraft extends Partial<TripBrief> {
  date_context?: Record<string, unknown>;
  transport_strategy?: TransportStrategy;
  pending_questions?: string[];
}

export interface ConversationMessage {
  id?: number;
  role: "assistant" | "user";
  kind: ConversationMessageKind;
  text?: string;
  questions?: string[];
  draft?: PlanningDraft;
  trip?: Trip;
  itinerary?: ItineraryDraft;
  job?: PlanningJob;
  jobId?: string;
  mapDayId?: string;
  intent?: TravelIntent;
  sources?: ChatSourceCitation[];
  usedTools?: string[];
  attachments?: UploadedAsset[];
}

export interface ChatMessage extends ConversationMessage {
  id: number;
}

export interface ConversationMessagePayload {
  id?: number;
  role: "assistant" | "user";
  kind: ConversationMessageKind;
  text?: string;
  questions?: string[];
  draft?: PlanningDraft;
  trip?: Trip;
  itinerary?: ItineraryDraft;
  job?: PlanningJob;
  job_id?: string;
  map_day_id?: string;
  intent?: TravelIntent;
  sources?: ChatSourceCitation[];
  used_tools?: string[];
  attachments?: ConversationAttachmentPayload[];
}

export interface ConversationAttachmentPayload {
  id: string;
  name: string;
  mime_type: string;
  kind: "image" | "document";
  size_bytes: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ConversationMessagePayload[];
  requirement_history: string[];
  planning_draft: PlanningDraft;
  trip_id: string | null;
  version: number;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  trip_id: string | null;
  planning_draft: PlanningDraft;
  version: number;
  message_count: number;
  preview: string;
  updated_at: string;
}

export interface ConversationList {
  items: ConversationSummary[];
}

export interface ConversationPayload {
  title: string;
  messages: ConversationMessagePayload[];
  requirement_history: string[];
  planning_draft?: PlanningDraft;
  trip_id?: string | null;
}
