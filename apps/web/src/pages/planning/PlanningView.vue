<!-- 文件说明：前端页面：PlanningView。 -->
<script setup lang="ts">
import {
  ArrowLeft,
  Bot,
  Check,
  CircleDashed,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { formatMoney } from "../../features/budget/form";
import { planningApi } from "../../features/planning/api";
import type {
  ItineraryDraft,
  PlanningEvent,
  PlanningJob,
} from "../../features/planning/types";
import { tripApi } from "../../features/trips/api";
import type { Trip } from "../../features/trips/types";
import { isVersionConflict } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const trip = ref<Trip | null>(null);
const loading = ref(true);
const running = ref(false);
const error = ref("");
const events = ref<PlanningEvent[]>([]);
const job = ref<PlanningJob | null>(null);
const draft = ref<ItineraryDraft | null>(null);

const tripId = computed(() =>
  typeof route.params.tripId === "string" ? route.params.tripId : "",
);

const eventLabels: Record<string, string> = {
  stage: "分析",
  tool_call: "工具",
  validation: "校验",
  complete: "完成",
  error: "失败",
};
const currentEvent = computed(() => events.value.at(-1) ?? null);

async function loadTrip(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  loading.value = true;
  error.value = "";
  try {
    trip.value = await tripApi.get(auth.token, tripId.value);
  } catch {
    error.value = "无法加载旅行需求。";
  } finally {
    loading.value = false;
  }
}

function applyJob(nextJob: PlanningJob): void {
  job.value = nextJob;
  events.value = nextJob.events;
  if (nextJob.result) draft.value = nextJob.result;
}

async function pollUntilFinished(jobId: string): Promise<PlanningJob | null> {
  if (!auth.token) return null;
  for (let attempt = 0; attempt < 15; attempt += 1) {
    const nextJob = await planningApi.get(auth.token, jobId);
    applyJob(nextJob);
    if (
      nextJob.status === "completed" ||
      nextJob.status === "partial" ||
      nextJob.status === "failed"
    ) {
      return nextJob;
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  return job.value;
}

async function generatePreview(): Promise<void> {
  if (!auth.token || !trip.value) return;
  running.value = true;
  error.value = "";
  draft.value = null;
  events.value = [];
  job.value = null;
  try {
    const started = await planningApi.start(
      auth.token,
      trip.value.id,
      trip.value.version,
      true,
    );
    try {
      await planningApi.streamEvents(auth.token, started.job_id, (event) => {
        events.value = [...events.value, event.data];
      });
    } catch {
      // Polling is the supported fallback when SSE disconnects.
    }
    const finalJob = await pollUntilFinished(started.job_id);
    if (finalJob?.status === "failed") {
      error.value = finalJob.error_message
        ? `规划任务失败：${finalJob.error_message}`
        : "规划任务失败，已记录错误事件。";
    } else if (finalJob?.status === "partial") {
      error.value = "规划返回部分结果，请检查未解决问题。";
    }
  } catch (cause) {
    error.value = isVersionConflict(cause)
      ? "旅行已在其他会话更新，请刷新后重试。"
      : "无法启动规划任务。";
  } finally {
    running.value = false;
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value}T00:00:00`));
}

function formatTime(value: string): string {
  return value.slice(11, 16);
}

onMounted(loadTrip);
</script>

<template>
  <main class="planning-page">
    <RouterLink class="back-link" :to="`/trips/${tripId}`">
      <ArrowLeft :size="16" :stroke-width="1.8" />
      返回旅行详情
    </RouterLink>

    <div v-if="loading" class="itinerary-loading" aria-label="正在加载规划页面">
      <span />
      <span />
    </div>

    <div v-else-if="!trip" class="trip-state-panel trip-state-panel--error">
      <strong>无法打开规划页面</strong>
      <span>{{ error }}</span>
      <button class="quiet-action" type="button" @click="loadTrip">
        <RefreshCw :size="16" :stroke-width="1.8" />
        重新加载
      </button>
    </div>

    <template v-else>
      <header class="planning-heading">
        <div>
          <h1>生成逐日行程</h1>
          <span>{{ trip.brief.destination }} · {{ trip.brief.start_date }} 至 {{ trip.brief.end_date }}</span>
        </div>
        <div class="planning-heading__actions">
          <span class="planner-badge">
            <Bot :size="15" :stroke-width="1.8" />
            LangGraph Agent
          </span>
          <button class="primary-button" type="button" :disabled="running" @click="generatePreview">
            <Play :size="16" :stroke-width="1.8" />
            {{ running ? "规划中" : "生成行程" }}
          </button>
        </div>
      </header>

      <p v-if="error" class="form-error" role="alert">{{ error }}</p>

      <div class="planning-layout">
        <section class="planner-brief" aria-labelledby="planner-brief-title">
          <header>
            <ShieldCheck :size="17" :stroke-width="1.7" />
            <div>
              <h2 id="planner-brief-title">已确认需求</h2>
            </div>
          </header>
          <dl>
            <div><dt>预算</dt><dd>{{ formatMoney(trip.brief.budget_minor ?? 0, trip.brief.currency) }}</dd></div>
            <div><dt>人数</dt><dd>{{ trip.brief.party_size }} 人</dd></div>
            <div><dt>节奏</dt><dd>{{ trip.brief.pace }}</dd></div>
            <div><dt>必去</dt><dd>{{ trip.brief.must_visit.join(" · ") || "未设置" }}</dd></div>
          </dl>
          <p>完成后写入逐日行程，可继续编辑。</p>
        </section>

        <section class="planner-progress" aria-labelledby="planner-progress-title">
          <header>
            <h2 id="planner-progress-title">任务进度</h2>
            <span>{{ job?.status || "尚未开始" }}</span>
          </header>
          <div class="planner-progress__bar">
            <span :style="{ transform: `scaleX(${(job?.progress ?? 0) / 100})` }" />
          </div>
          <div v-if="currentEvent" class="planner-current-event">
            <Check
              v-if="currentEvent.type === 'complete'"
              :size="14"
              :stroke-width="1.8"
            />
            <CircleDashed v-else :size="14" :stroke-width="1.8" />
            <span>
              <strong>{{ eventLabels[currentEvent.type] || currentEvent.type }}</strong>
              <small>{{ currentEvent.message }}</small>
            </span>
          </div>
          <p v-else class="planner-progress__empty">生成后将显示规划事件。</p>
          <details v-if="events.length > 1" class="planner-event-log">
            <summary>查看全部步骤（{{ events.length }}）</summary>
            <ol>
              <li v-for="event in events" :key="event.sequence">
                <strong>{{ eventLabels[event.type] || event.type }}</strong>
                <small>{{ event.message }}</small>
              </li>
            </ol>
          </details>
        </section>
      </div>

      <section
        v-if="draft"
        class="planner-draft"
        data-testid="planner-draft"
        aria-labelledby="planner-draft-title"
      >
        <header>
          <div>
            <h2 id="planner-draft-title">已生成行程</h2>
            <span>
              {{ draft.days.length }} 天 ·
              {{ job?.tool_call_count ?? 0 }} 次工具调用 ·
              {{ job?.loop_count ?? 0 }} 轮修复
            </span>
          </div>
          <span v-if="job?.status === 'completed'" class="planner-complete">
            <Check :size="14" :stroke-width="1.8" />
            规划完成
          </span>
        </header>
        <RouterLink
          v-if="job?.status === 'completed'"
          class="quiet-action planner-draft__open"
          :to="`/trips/${tripId}/itinerary`"
        >
          打开逐日行程
        </RouterLink>
        <ul v-if="draft.validation_summary.length" class="planner-issues">
          <li
            v-for="issue in draft.validation_summary"
            :key="`${issue.path}-${issue.code}`"
            :class="`planner-issues--${issue.severity}`"
          >
            <strong>{{ issue.message }}</strong>
            <span v-if="issue.repair_hint">{{ issue.repair_hint }}</span>
          </li>
        </ul>
        <div class="planner-days">
          <article v-for="day in draft.days" :key="day.id" data-testid="draft-day">
            <header>
              <span>Day {{ day.id.replace('day-', '') }}</span>
              <h3>{{ formatDate(day.date) }}</h3>
              <p>{{ day.theme }}</p>
            </header>
            <div>
              <div v-for="stop in day.stops" :key="stop.id">
                <time>{{ formatTime(stop.start_at) }}</time>
                <strong>{{ stop.place_name }}</strong>
                <span>{{ stop.duration_minutes }} 分钟 · {{ stop.source.provider }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>
    </template>
  </main>
</template>
