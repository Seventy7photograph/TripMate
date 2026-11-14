// 文件说明：Pinia 状态仓库：conversation。
import { computed, ref } from "vue";
import { defineStore } from "pinia";

import type {
  ChatMessage,
  Conversation,
  ConversationSummary,
} from "../features/chat/types";

export const ACTIVE_CONVERSATION_KEY =
  "tripmate.active-conversation-id";

function readActiveConversationId(): string | null {
  return typeof window === "undefined"
    ? null
    : window.sessionStorage.getItem(ACTIVE_CONVERSATION_KEY);
}

function persistActiveConversationId(conversationId: string | null): void {
  if (typeof window === "undefined") return;
  if (conversationId) {
    window.sessionStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId);
  } else {
    window.sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }
}

export const useConversationStore = defineStore("conversation", () => {
  const messages = ref<ChatMessage[]>([]);
  const requirementHistory = ref<string[]>([]);
  const conversationId = ref<string | null>(null);
  const conversationVersion = ref(0);
  const conversationTripId = ref<string | null>(null);
  const historyItems = ref<ConversationSummary[]>([]);
  const initialized = ref(false);

  const hasConversation = computed(() => messages.value.length > 0);

  function applyConversation(conversation: Conversation): void {
    conversationId.value = conversation.id;
    persistActiveConversationId(conversation.id);
    conversationVersion.value = conversation.version;
    conversationTripId.value = conversation.trip_id;
    requirementHistory.value = [...conversation.requirement_history];
    messages.value = conversation.messages.map((message, index) => ({
      ...message,
      id: message.id ?? index + 1,
      jobId: message.job_id,
      mapDayId: message.map_day_id,
      usedTools: message.used_tools,
    }));
    initialized.value = true;
  }

  function resetConversation(): void {
    messages.value = [];
    requirementHistory.value = [];
    conversationId.value = null;
    conversationVersion.value = 0;
    conversationTripId.value = null;
    persistActiveConversationId(null);
    initialized.value = true;
  }

  function resetAll(): void {
    resetConversation();
    historyItems.value = [];
    initialized.value = false;
  }

  return {
    messages,
    requirementHistory,
    conversationId,
    conversationVersion,
    conversationTripId,
    historyItems,
    activeConversationId: readActiveConversationId,
    initialized,
    hasConversation,
    applyConversation,
    resetConversation,
    resetAll,
  };
});
