// 文件说明：Pinia 状态仓库：conversation.test。
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useConversationStore } from "./conversation";

describe("conversation store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("keeps a conversation snapshot across route component remounts", () => {
    const store = useConversationStore();
    store.applyConversation({
      id: "conversation-1",
      title: "重庆",
      messages: [
        { id: 1, role: "user", kind: "text", text: "去重庆" },
        {
          id: 2,
          role: "assistant",
          kind: "plan",
          text: "已生成",
        },
      ],
      requirement_history: ["去重庆"],
      trip_id: "trip-1",
      version: 3,
      message_count: 2,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });

    expect(store.hasConversation).toBe(true);
    expect(store.messages[1]?.text).toBe("已生成");
  });

  it("clears cached history when the authenticated session ends", () => {
    const store = useConversationStore();
    store.applyConversation({
      id: "conversation-1",
      title: "重庆",
      messages: [{ id: 1, role: "user", kind: "text", text: "去重庆" }],
      requirement_history: ["去重庆"],
      trip_id: null,
      version: 1,
      message_count: 1,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });

    store.resetAll();

    expect(store.hasConversation).toBe(false);
    expect(store.historyItems).toEqual([]);
  });
});
