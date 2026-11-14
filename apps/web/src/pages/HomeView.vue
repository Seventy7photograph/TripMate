<!-- 文件说明：前端页面：HomeView。 -->
<script setup lang="ts">
import {
  CalendarDays,
  FileText,
  History,
  Image,
  LoaderCircle,
  MapPin,
  MessageSquarePlus,
  Sparkles,
  UsersRound,
  WalletCards,
  X,
} from "lucide-vue-next";
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import FlowerActionButton from "../components/FlowerActionButton.vue";
import LeafActionButton from "../components/LeafActionButton.vue";
import { travelChatApi } from "../features/chat/agentApi";
import { conversationApi } from "../features/chat/api";
import TravelPlanCard from "../features/chat/TravelPlanCard.vue";
import type {
  ChatMessage,
  ConversationMessagePayload,
  ConversationPayload,
  ChatSourceCitation,
  TravelChatHistoryTurn,
} from "../features/chat/types";
import { planningApi } from "../features/planning/api";
import type { PlanningJob } from "../features/planning/types";
import { itineraryApi } from "../features/itinerary/api";
import { tripApi } from "../features/trips/api";
import type { Trip, TripBrief } from "../features/trips/types";
import ChatAttachmentPicker from "../features/upload/ChatAttachmentPicker.vue";
import { uploadApi } from "../features/upload/api";
import type {
  PendingAttachment,
  UploadedAsset,
} from "../features/upload/types";
import { useAuthStore } from "../stores/auth";
import {
  ACTIVE_CONVERSATION_KEY,
  useConversationStore,
} from "../stores/conversation";

const auth = useAuthStore();
const conversationStore = useConversationStore();
const {
  messages,
  requirementHistory,
  conversationId,
  conversationVersion,
  conversationTripId,
  historyItems: conversationHistory,
} = storeToRefs(conversationStore);
const route = useRoute();
const router = useRouter();
const videoSource = "/media/travel-backdrop.mp4";
const prompt = ref("");
const pendingAttachments = ref<PendingAttachment[]>([]);
const busy = ref(false);
const composerShrinking = ref(false);
const error = ref("");
const guestLoginPromptOpen = ref(false);
const messageCursor = ref(0);
const conversationEnd = ref<HTMLElement | null>(null);
const historyOpen = ref(false);
const historyLoading = ref(false);
const historyError = ref("");
const persistenceError = ref("");
let persistenceQueue: Promise<unknown> = Promise.resolve();
const GUEST_DRAFT_KEY = "tripmate.guest-prompt-draft";

const suggestions = [
  "2026年12月1日到12月3日，2个人从上海去重庆，预算5000元，喜欢美食和夜景。",
  "2026年12月12日到12月15日，3个人从杭州去泉州，预算8000元，想看古建、吃小吃。",
  "2027年1月2日到1月6日，2个人从北京去大阪，预算12000元，喜欢咖啡和城市漫步。",
];

const hasConversation = computed(() => messages.value.length > 0);
const canSubmit = computed(
  () =>
    (prompt.value.trim().length > 0 || pendingAttachments.value.length > 0) &&
    !busy.value,
);
const composerActionLabel = computed(() => {
  if (busy.value) return hasConversation.value ? "发送中" : "规划中";
  return hasConversation.value ? "发送" : "开始规划";
});
const activeDraft = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const draft = messages.value[index]?.draft;
    if (draft) return draft;
  }
  return null;
});

function nextId(): number {
  messageCursor.value += 1;
  return messageCursor.value;
}

function conversationTitle(): string {
  const destination = activeDraft.value?.destination?.trim();
  if (destination) return destination;
  const firstUserMessage = messages.value.find(
    (message) => message.role === "user" && message.text?.trim(),
  );
  if (firstUserMessage?.text?.trim()) {
    return firstUserMessage.text.trim().slice(0, 80);
  }
  const firstAttachment = messages.value.find(
    (message) => message.role === "user" && message.attachments?.length,
  )?.attachments?.[0]?.name;
  return firstAttachment?.slice(0, 80) || "新的旅行对话";
}

function snapshotPayload(): ConversationPayload {
  return {
    title: conversationTitle(),
    messages: messages.value.map(serializeMessage),
    requirement_history: [...requirementHistory.value],
    trip_id: conversationTripId.value,
  };
}

function serializeMessage(message: ChatMessage): ConversationMessagePayload {
  return {
    id: message.id,
    role: message.role,
    kind: message.kind,
    text: message.text,
    questions: message.questions,
    draft: message.draft,
    trip: message.trip,
    itinerary: message.itinerary,
    job: message.job,
    job_id: message.jobId,
    map_day_id: message.mapDayId,
    intent: message.intent,
    sources: message.sources,
    used_tools: message.usedTools,
    attachments: message.attachments,
  };
}

function travelHistory(): TravelChatHistoryTurn[] {
  return messages.value
    .filter(
      (message): message is ChatMessage & { text: string } =>
        Boolean(message.text?.trim()),
    )
    .slice(-12)
    .map((message) => ({
      role: message.role,
      content: message.text.trim().slice(0, 8_000),
    }));
}

function sourceLabel(source: ChatSourceCitation): string {
  if (source.title?.trim()) return source.title.trim();
  try {
    return new URL(source.url).hostname;
  } catch {
    return source.url;
  }
}

function sourceHost(source: ChatSourceCitation): string {
  try {
    return new URL(source.url).hostname;
  } catch {
    return "";
  }
}

function answerBlocks(text: string | undefined): Array<{
  type: "heading" | "bullet" | "text";
  text: string;
}> {
  // 只渲染受控的 Markdown 子集为文本节点，禁止使用 v-html。
  if (!text) return [];
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const clean = line
        .replace(/\*\*/g, "")
        .replace(/`/g, "")
        .replace(/[\u{1F300}-\u{1FAFF}\u2600-\u27BF]/gu, "")
        .trim();
      if (/^#{1,6}\s+/.test(clean)) {
        return {
          type: "heading" as const,
          text: clean.replace(/^#{1,6}\s+/, ""),
        };
      }
      if (/^[*+-]\s+/.test(clean)) {
        return {
          type: "bullet" as const,
          text: clean.replace(/^[*+-]\s+/, ""),
        };
      }
      return { type: "text" as const, text: clean };
    });
}

function persistConversation(): Promise<void> {
  const token = auth.token;
  if (!token) return Promise.resolve();
  const payload = snapshotPayload();
  persistenceQueue = persistenceQueue
    .then(async () => {
      persistenceError.value = "";
      if (conversationId.value) {
        const updated = await conversationApi.update(
          token,
          conversationId.value,
          conversationVersion.value,
          payload,
        );
        conversationVersion.value = updated.version;
      } else {
        const created = await conversationApi.create(token, payload);
        conversationId.value = created.id;
        conversationVersion.value = created.version;
        window.sessionStorage.setItem(ACTIVE_CONVERSATION_KEY, created.id);
      }
    })
    .catch(() => {
      persistenceError.value = "历史对话暂时无法保存，请稍后重试。";
    });
  return persistenceQueue.then(() => undefined);
}

async function refreshHistory(): Promise<void> {
  if (!auth.token) return;
  historyLoading.value = true;
  historyError.value = "";
  try {
    conversationHistory.value = (await conversationApi.list(auth.token)).items;
  } catch {
    historyError.value = "历史对话加载失败。";
  } finally {
    historyLoading.value = false;
  }
}

async function loadConversation(id: string): Promise<void> {
  if (!auth.token) return;
  historyLoading.value = true;
  historyError.value = "";
  try {
    const conversation = await conversationApi.get(auth.token, id);
    conversationStore.applyConversation(conversation);
    messageCursor.value = messages.value.reduce(
      (maximum, message) => Math.max(maximum, message.id),
      0,
    );
    historyOpen.value = false;
    await scrollToLatest();
    void resumeWorkingMessages();
  } catch {
    historyError.value = "这段历史对话无法打开。";
  } finally {
    historyLoading.value = false;
  }
}

async function openHistory(): Promise<void> {
  if (!auth.token) {
    await router.push({
      name: "login",
      query: { redirect: route.fullPath },
    });
    return;
  }
  historyOpen.value = !historyOpen.value;
  if (historyOpen.value) await refreshHistory();
}

async function scrollToLatest(): Promise<void> {
  await nextTick();
  if (typeof conversationEnd.value?.scrollIntoView === "function") {
    conversationEnd.value.scrollIntoView({ behavior: "smooth", block: "end" });
  }
}

async function pollJob(jobId: string): Promise<PlanningJob> {
  if (!auth.token) throw new Error("Not authenticated");
  let job = await planningApi.get(auth.token, jobId);
  for (
    let attempt = 0;
    attempt < 120 &&
    !["completed", "partial", "failed"].includes(job.status);
    attempt += 1
  ) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    job = await planningApi.get(auth.token, jobId);
  }
  return job;
}

async function finalizeWorkingMessage(
  workingId: number,
  trip: Trip,
  job: PlanningJob,
): Promise<void> {
  const workingIndex = messages.value.findIndex(
    (message) => message.id === workingId,
  );
  if (workingIndex < 0 || !auth.token) return;
  if (["completed", "partial"].includes(job.status) && job.result) {
    const persistedItinerary =
      job.status === "completed"
        ? await itineraryApi.get(auth.token, trip.id)
        : null;
    messages.value[workingIndex] = {
      id: workingId,
      role: "assistant",
      kind: "plan",
      trip,
      itinerary: job.result,
      job,
      jobId: job.id,
      mapDayId: persistedItinerary?.days[0]?.id,
      draft: trip.brief,
    };
  } else {
    const reason = job.error_message?.trim();
    messages.value[workingIndex] = {
      id: workingId,
      role: "assistant",
      kind: "text",
      text: reason
        ? `行程生成未完成：${reason}。旅行已保存，可以打开详情后重试。`
        : "行程生成未完成，旅行已保存，可以打开详情后重试。",
      trip,
      job,
      jobId: job.id,
      draft: trip.brief,
    };
  }
  conversationTripId.value = trip.id;
  await persistConversation();
}

async function resumeWorkingMessages(): Promise<void> {
  if (!auth.token) return;
  const pending = messages.value.filter(
    (message) =>
      message.kind === "working" &&
      Boolean(message.trip) &&
      Boolean(message.jobId),
  );
  for (const message of pending) {
    if (!message.trip || !message.jobId) continue;
    try {
      const job = await pollJob(message.jobId);
      await finalizeWorkingMessage(message.id, message.trip, job);
    } catch {
      persistenceError.value = "未完成的规划暂时无法恢复。";
    }
  }
  await scrollToLatest();
}

function briefFacts(draft: Partial<TripBrief>): Array<{
  label: string;
  value: string;
  icon: typeof MapPin;
}> {
  const facts = [];
  if (draft.destination) {
    facts.push({ label: "目的地", value: draft.destination, icon: MapPin });
  }
  if (draft.start_date && draft.end_date) {
    facts.push({
      label: "日期",
      value: `${draft.start_date} 至 ${draft.end_date}`,
      icon: CalendarDays,
    });
  }
  if (draft.party_size) {
    facts.push({
      label: "人数",
      value: `${draft.party_size} 人`,
      icon: UsersRound,
    });
  }
  if (draft.budget_minor) {
    facts.push({
      label: "预算",
      value: `¥${(draft.budget_minor / 100).toLocaleString("zh-CN")}`,
      icon: WalletCards,
    });
  }
  return facts;
}

function handleComposerKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  void submitPrompt();
}

function handleGuestComposerPointerDown(event: PointerEvent): void {
  if (auth.token) return;
  event.preventDefault();
  guestLoginPromptOpen.value = true;
}

function handleGuestComposerFocus(): void {
  if (!auth.token) guestLoginPromptOpen.value = true;
}

function cancelGuestLogin(): void {
  guestLoginPromptOpen.value = false;
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }
}

async function confirmGuestLogin(): Promise<void> {
  if (prompt.value) {
    window.sessionStorage.setItem(GUEST_DRAFT_KEY, prompt.value);
  }
  guestLoginPromptOpen.value = false;
  await router.push({
    name: "login",
    query: { redirect: route.fullPath },
  });
}

async function submitPrompt(): Promise<void> {
  const text = prompt.value.trim();
  if ((!text && !pendingAttachments.value.length) || busy.value) return;
  if (!auth.token) {
    guestLoginPromptOpen.value = true;
    return;
  }

  error.value = "";
  persistenceError.value = "";
  busy.value = true;
  const attachmentsToUpload = [...pendingAttachments.value];
  const uploaded: UploadedAsset[] = [];
  try {
    for (const attachment of attachmentsToUpload) {
      uploaded.push(await uploadApi.upload(auth.token, attachment.file));
    }
  } catch (cause) {
    for (const asset of uploaded) {
      void uploadApi.remove(auth.token, asset.id).catch(() => undefined);
    }
    error.value =
      cause instanceof Error && cause.message
        ? cause.message
        : "附件上传失败，请稍后重试。";
    busy.value = false;
    return;
  }
  // 首轮先播放输入框收缩动画，后续会话保持同一发送按钮。
  const isFirstTurn = messages.value.length === 0;
  const history = travelHistory();
  if (isFirstTurn) {
    composerShrinking.value = true;
    await new Promise((resolve) => window.setTimeout(resolve, 240));
  }
  messages.value.push({
    id: nextId(),
    role: "user",
    kind: "text",
    text: text || undefined,
    attachments: uploaded,
  });
  requirementHistory.value.push(
    text || `附件：${uploaded.map((asset) => asset.name).join("、")}`,
  );
  prompt.value = "";
  clearPendingAttachments();
  composerShrinking.value = false;
  void persistConversation();
  await scrollToLatest();

  try {
    // 先让 Agent 判断意图；只有完整规划请求才继续创建 Trip 和启动 Graph。
    const chat = await travelChatApi.respond(
      auth.token,
      text || `请根据附件理解旅行需求：${uploaded.map((asset) => asset.name).join("、")}`,
      uploaded.map((asset) => asset.id),
      history,
    );
    if (chat.questions.length > 0) {
      messages.value.push({
        id: nextId(),
        role: "assistant",
        kind: "questions",
        text: "还需要确认：",
        questions: chat.questions,
        draft: chat.draft || undefined,
        intent: chat.intent,
      });
      void persistConversation();
      return;
    }
    if (!chat.requires_planning || !chat.brief) {
      messages.value.push({
        id: nextId(),
        role: "assistant",
        kind: "answer",
        text: chat.answer || "暂时没有得到可用答复，请换一种说法再试。",
        intent: chat.intent,
        sources: chat.sources,
        usedTools: chat.used_tools,
      });
      void persistConversation();
      return;
    }

    const workingId = nextId();
    messages.value.push({
      id: workingId,
      role: "assistant",
      kind: "working",
      text: "正在检索地点并生成行程",
      draft: chat.draft || undefined,
      intent: chat.intent,
    });
    void persistConversation();

    const trip = await tripApi.create(auth.token, { brief: chat.brief });
    conversationTripId.value = trip.id;
    const pendingIndex = messages.value.findIndex(
      (message) => message.id === workingId,
    );
    if (pendingIndex >= 0) {
      messages.value[pendingIndex] = {
        ...messages.value[pendingIndex]!,
        trip,
      };
    }
    void persistConversation();
    const started = await planningApi.start(
      auth.token,
      trip.id,
      trip.version,
      true,
    );
    const startedIndex = messages.value.findIndex(
      (message) => message.id === workingId,
    );
    if (startedIndex >= 0) {
      messages.value[startedIndex] = {
        ...messages.value[startedIndex]!,
        jobId: started.job_id,
      };
    }
    void persistConversation();
    const job = await pollJob(started.job_id);
    await finalizeWorkingMessage(workingId, trip, job);
    await refreshHistory();
  } catch (cause) {
    error.value =
      cause instanceof Error && cause.message
        ? cause.message
        : "暂时无法完成规划，请稍后重试。";
    messages.value.push({
      id: nextId(),
      role: "assistant",
      kind: "text",
      text: "连接旅行助手失败，请重新发送一次。",
    });
    void persistConversation();
  } finally {
    busy.value = false;
    await scrollToLatest();
  }
}

async function useSuggestion(value: string): Promise<void> {
  prompt.value = value;
  await submitPrompt();
}

async function resetConversation(): Promise<void> {
  if (messages.value.length) await persistConversation();
  conversationStore.resetConversation();
  prompt.value = "";
  clearPendingAttachments();
  error.value = "";
  persistenceError.value = "";
  historyOpen.value = false;
  composerShrinking.value = false;
}

function clearPendingAttachments(): void {
  pendingAttachments.value.forEach((attachment) => {
    if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
  });
  pendingAttachments.value = [];
}

onMounted(async () => {
  const savedDraft = window.sessionStorage.getItem(GUEST_DRAFT_KEY);
  if (savedDraft !== null) {
    prompt.value = savedDraft;
    window.sessionStorage.removeItem(GUEST_DRAFT_KEY);
  }
  if (!auth.token) return;
  const activeConversationId = window.sessionStorage.getItem(
    ACTIVE_CONVERSATION_KEY,
  );
  if (!conversationStore.hasConversation && activeConversationId) {
    await loadConversation(activeConversationId);
  }
});

</script>

<template>
  <main class="home-page">
    <video
      class="home-backdrop-video"
      autoplay
      muted
      loop
      playsinline
      aria-hidden="true"
    >
      <source :src="videoSource" type="video/mp4" />
    </video>
    <div class="home-backdrop-overlay" aria-hidden="true" />

    <div class="home-quick-actions" aria-label="对话操作">
      <button type="button" @click="openHistory">
        <History :size="16" :stroke-width="1.8" />
        历史对话
      </button>
      <button v-if="hasConversation" type="button" @click="resetConversation">
        <MessageSquarePlus :size="16" :stroke-width="1.8" />
        新对话
      </button>
    </div>

    <Transition name="history-panel">
      <section
        v-if="historyOpen"
        class="conversation-history-panel"
        aria-label="历史对话"
      >
        <header>
          <strong>历史对话</strong>
          <button type="button" aria-label="关闭历史对话" @click="historyOpen = false">
            <X :size="14" :stroke-width="1.8" />
          </button>
        </header>
        <p v-if="historyLoading" class="conversation-history-panel__state">
          正在加载
        </p>
        <p v-else-if="historyError" class="conversation-history-panel__state">
          {{ historyError }}
        </p>
        <p
          v-else-if="conversationHistory.length === 0"
          class="conversation-history-panel__state"
        >
          还没有已保存的对话
        </p>
        <div v-else class="conversation-history-list">
          <button
            v-for="conversation in conversationHistory"
            :key="conversation.id"
            class="conversation-history-item"
            type="button"
            @click="loadConversation(conversation.id)"
          >
            <span>
              <strong>{{ conversation.title }}</strong>
              <small>{{ conversation.preview }}</small>
            </span>
            <time :datetime="conversation.updated_at">
              {{
                new Intl.DateTimeFormat("zh-CN", {
                  month: "numeric",
                  day: "numeric",
                }).format(new Date(conversation.updated_at))
              }}
            </time>
          </button>
        </div>
      </section>
    </Transition>

    <div class="home-content" :class="{ 'home-content--thread': hasConversation }">
      <section v-if="!hasConversation" class="home-hero">
        <h1>新的故事，从哪里开始？</h1>
        <p>问我目的地、行程、交通、预算，或旅途中的任何问题。</p>

        <form
          class="home-composer"
          :class="{ 'home-composer--shrinking': composerShrinking }"
          @submit.prevent="submitPrompt"
        >
          <label class="sr-only" for="travel-prompt">旅行问题或需求</label>
          <textarea
            id="travel-prompt"
            v-model="prompt"
            rows="5"
            maxlength="50000"
            placeholder="例如：2026年12月1日到12月3日，2个人从上海去重庆，预算5000元，喜欢美食和夜景。"
            @keydown="handleComposerKeydown"
            @pointerdown="handleGuestComposerPointerDown"
            @focus="handleGuestComposerFocus"
          />
          <div class="home-composer__footer">
            <div class="home-composer__tools">
              <ChatAttachmentPicker
                :attachments="pendingAttachments"
                :disabled="busy"
                @update:attachments="pendingAttachments = $event"
              />
            </div>
            <FlowerActionButton
              :label="composerActionLabel"
              :busy="busy"
              :disabled="!canSubmit"
            />
          </div>
        </form>

        <div class="home-suggestions" aria-label="旅行灵感">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion"
            type="button"
            @click="useSuggestion(suggestion)"
          >
            {{ suggestion.split("，")[0] }}
          </button>
        </div>
      </section>

      <section v-else class="agent-thread-shell">
        <header class="agent-thread-heading">
          <div>
            <Sparkles :size="17" :stroke-width="1.8" />
            <span>{{ activeDraft?.destination || "旅行对话" }}</span>
          </div>
        </header>

        <div class="agent-thread" aria-live="polite">
          <template v-for="message in messages" :key="message.id">
            <div
              v-if="message.role === 'user'"
              class="agent-message agent-message--user"
            >
              <p v-if="message.text">{{ message.text }}</p>
              <div v-if="message.attachments?.length" class="message-attachments">
                <span
                  v-for="attachment in message.attachments"
                  :key="attachment.id"
                  class="message-attachment"
                >
                  <component
                    :is="attachment.kind === 'image' ? Image : FileText"
                    :size="14"
                  />
                  {{ attachment.name }}
                </span>
              </div>
            </div>

            <div
              v-else
              class="agent-message agent-message--assistant"
              :class="`agent-message--${message.kind}`"
            >
              <template v-if="message.kind === 'questions'">
                <p>{{ message.text }}</p>
                <div
                  v-if="message.draft && briefFacts(message.draft).length"
                  class="agent-brief-facts"
                >
                  <span
                    v-for="fact in briefFacts(message.draft)"
                    :key="fact.label"
                  >
                    <component :is="fact.icon" :size="14" :stroke-width="1.8" />
                    <small>{{ fact.label }}</small>
                    <strong>{{ fact.value }}</strong>
                  </span>
                </div>
                <ul class="agent-questions">
                  <li v-for="question in message.questions" :key="question">
                    {{ question }}
                  </li>
                </ul>
              </template>

              <template v-else-if="message.kind === 'working'">
                <span class="agent-working-mark">
                  <LoaderCircle :size="16" :stroke-width="1.8" class="is-spinning" />
                </span>
                <span>{{ message.text }}</span>
              </template>

              <template v-else-if="message.kind === 'plan' && message.trip && message.itinerary">
                <TravelPlanCard
                  :trip="message.trip"
                  :itinerary="message.itinerary"
                  :map-day-id="message.mapDayId"
                  :status="message.job?.status === 'partial' ? 'partial' : 'completed'"
                />
              </template>

              <template v-else-if="message.kind === 'answer'">
                <div class="agent-answer-copy">
                  <template
                    v-for="(block, index) in answerBlocks(message.text)"
                    :key="`${message.id}-${index}`"
                  >
                    <strong v-if="block.type === 'heading'">
                      {{ block.text }}
                    </strong>
                    <p
                      v-else
                      :class="{ 'agent-answer-copy__bullet': block.type === 'bullet' }"
                    >
                      {{ block.text }}
                    </p>
                  </template>
                </div>
                <details
                  v-if="message.sources?.length"
                  class="agent-sources"
                >
                  <summary>
                    引用来源
                    <span>{{ message.sources.length }}</span>
                  </summary>
                  <ul>
                    <li
                      v-for="source in message.sources"
                      :key="source.url"
                    >
                      <a
                        :href="source.url"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <span>{{ sourceLabel(source) }}</span>
                        <small>{{ sourceHost(source) }}</small>
                      </a>
                    </li>
                  </ul>
                </details>
              </template>

              <template v-else>
                <span>{{ message.text }}</span>
                <RouterLink
                  v-if="message.trip"
                  class="agent-inline-link"
                  :to="`/trips/${message.trip.id}`"
                >
                  打开旅行
                </RouterLink>
              </template>
            </div>
          </template>
          <div ref="conversationEnd" />
        </div>

        <p v-if="error" class="home-inline-error" role="alert">{{ error }}</p>
        <p v-if="persistenceError" class="home-inline-error" role="status">
          {{ persistenceError }}
        </p>

        <form class="home-composer home-composer--thread" @submit.prevent="submitPrompt">
          <label class="sr-only" for="travel-prompt-followup">继续补充旅行需求</label>
          <textarea
            id="travel-prompt-followup"
            v-model="prompt"
            rows="2"
            maxlength="50000"
            placeholder="继续补充，或描述下一次旅行。"
            @keydown="handleComposerKeydown"
            @pointerdown="handleGuestComposerPointerDown"
            @focus="handleGuestComposerFocus"
          />
          <div class="home-composer__footer">
            <div class="home-composer__tools">
              <ChatAttachmentPicker
                :attachments="pendingAttachments"
                :disabled="busy"
                @update:attachments="pendingAttachments = $event"
              />
              <span v-if="busy">正在处理</span>
            </div>
            <FlowerActionButton
              :label="composerActionLabel"
              :busy="busy"
              :disabled="!canSubmit"
            />
          </div>
        </form>
      </section>
    </div>

    <Transition name="dialog-fade">
      <div
        v-if="guestLoginPromptOpen"
        class="dialog-backdrop"
        role="presentation"
        @click.self="cancelGuestLogin"
      >
        <section
          class="confirm-dialog guest-login-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="guest-login-title"
        >
          <header>
            <h2 id="guest-login-title">登录后开始规划</h2>
          </header>
          <p>
            登录后可以保存对话、生成行程并继续编辑。当前输入会在登录后恢复。
          </p>
          <footer>
            <button class="quiet-action" type="button" @click="cancelGuestLogin">
              继续浏览
            </button>
            <LeafActionButton
              class="guest-login-confirm"
              label="去登录"
              @click="confirmGuestLogin"
            />
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
