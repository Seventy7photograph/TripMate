// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  Conversation,
  ConversationList,
  ConversationPayload,
} from "./types";

export const conversationApi = {
  create(token: string, payload: ConversationPayload): Promise<Conversation> {
    return request<Conversation>(
      "/api/v1/conversations",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token,
    );
  },

  list(token: string): Promise<ConversationList> {
    return request<ConversationList>("/api/v1/conversations", {}, token);
  },

  get(token: string, conversationId: string): Promise<Conversation> {
    return request<Conversation>(
      `/api/v1/conversations/${conversationId}`,
      {},
      token,
    );
  },

  update(
    token: string,
    conversationId: string,
    expectedVersion: number,
    payload: ConversationPayload,
  ): Promise<Conversation> {
    return request<Conversation>(
      `/api/v1/conversations/${conversationId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: expectedVersion,
          ...payload,
        }),
      },
      token,
    );
  },
};
