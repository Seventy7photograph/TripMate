// 文件说明：前端功能模块：agentApi。
import { request } from "../../lib/http";
import type {
  TravelChatHistoryTurn,
  TravelChatResponse,
} from "./types";

function formatLocalDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export const travelChatApi = {
  respond(
    token: string,
    message: string,
    attachmentIds: string[] = [],
    history: TravelChatHistoryTurn[] = [],
    conversationId: string | null = null,
    clientToday: Date = new Date(),
  ): Promise<TravelChatResponse> {
    return request<TravelChatResponse>(
      "/api/v1/chat/respond",
      {
        method: "POST",
        body: JSON.stringify({
          message,
          attachment_ids: attachmentIds,
          history,
          conversation_id: conversationId,
          client_today: formatLocalDate(clientToday),
        }),
      },
      token,
    );
  },
};
