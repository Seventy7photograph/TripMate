// 文件说明：前端功能模块：agentApi。
import { request } from "../../lib/http";
import type {
  TravelChatHistoryTurn,
  TravelChatResponse,
} from "./types";

export const travelChatApi = {
  respond(
    token: string,
    message: string,
    attachmentIds: string[] = [],
    history: TravelChatHistoryTurn[] = [],
  ): Promise<TravelChatResponse> {
    return request<TravelChatResponse>(
      "/api/v1/chat/respond",
      {
        method: "POST",
        body: JSON.stringify({
          message,
          attachment_ids: attachmentIds,
          history,
        }),
      },
      token,
    );
  },
};
