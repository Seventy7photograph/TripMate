<!-- 文件说明：前端页面：TripItineraryView。 -->
<script setup lang="ts">
import {
  ArrowLeft,
  CalendarDays,
  History,
  Map,
  Plus,
  RefreshCw,
  WandSparkles,
  Wallet,
  X,
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { itineraryApi } from "../../features/itinerary/api";
import { datesBetween } from "../../features/itinerary/form";
import ItineraryDayEditor from "../../features/itinerary/ItineraryDayEditor.vue";
import ItineraryDiff from "../../features/itinerary/ItineraryDiff.vue";
import { patchApi } from "../../features/itinerary/patchApi";
import type { ItineraryPatch } from "../../features/itinerary/patchTypes";
import type {
  CreateStopInput,
  Itinerary,
  ItineraryStop,
  TripDay,
} from "../../features/itinerary/types";
import VersionConflictDialog from "../../features/itinerary/VersionConflictDialog.vue";
import VersionHistoryDialog from "../../features/itinerary/VersionHistoryDialog.vue";
import { tripApi } from "../../features/trips/api";
import type { Trip, TripVersionHistory } from "../../features/trips/types";
import {
  ApiError,
  conflictDetails,
  isVersionConflict,
} from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

interface ConflictState {
  currentVersion: number;
  localLabel: string;
  localPayload: unknown;
  serverItinerary: Itinerary;
  retry: (expectedVersion: number) => Promise<void>;
  draftStopId?: string;
}

const auth = useAuthStore();
const route = useRoute();
const trip = ref<Trip | null>(null);
const itinerary = ref<Itinerary | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const generating = ref(false);
const addingDayId = ref<string | null>(null);
const savingStopId = ref<string | null>(null);
const movingStopId = ref<string | null>(null);
const error = ref("");
const message = ref("");
const addErrors = reactive<Record<string, string>>({});
const addResetKeys = reactive<Record<string, number>>({});
const dayMessages = reactive<Record<string, string>>({});
const draftResetKeys = reactive<Record<string, number>>({});
const conflict = ref<ConflictState | null>(null);
const conflictApplying = ref(false);
const conflictCopyStatus = ref("");
const historyOpen = ref(false);
const historyLoading = ref(false);
const historyError = ref("");
const history = ref<TripVersionHistory | null>(null);
const restoringVersion = ref<number | null>(null);
const replanOpen = ref(false);
const replanDayId = ref("");
const replanInstruction = ref("");
const replanLoading = ref(false);
const replanError = ref("");
const patch = ref<ItineraryPatch | null>(null);
const patchApplying = ref(false);
const patchError = ref("");
const activeDayId = ref("");

let writeQueue: Promise<unknown> = Promise.resolve();

const tripId = computed(() =>
  typeof route.params.tripId === "string" ? route.params.tripId : "",
);

const dateRange = computed(() => {
  if (!trip.value) return "";
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  return `${formatter.format(new Date(`${trip.value.brief.start_date}T00:00:00`))} - ${formatter.format(
    new Date(`${trip.value.brief.end_date}T00:00:00`),
  )}`;
});

const missingDates = computed(() => {
  if (!trip.value || !itinerary.value) return [];
  const existing = new Set(itinerary.value.days.map((day) => day.date));
  return datesBetween(
    trip.value.brief.start_date,
    trip.value.brief.end_date,
  ).filter((dayDate) => !existing.has(dayDate));
});

const stopCount = computed(
  () => itinerary.value?.days.reduce((total, day) => total + day.stops.length, 0) ?? 0,
);
const days = computed(() => itinerary.value?.days ?? []);
const activeDay = computed(
  () => days.value.find((day) => day.id === activeDayId.value) ?? null,
);

function enqueueWrite<T>(operation: () => Promise<T>): Promise<T> {
  const next = writeQueue.then(operation, operation);
  writeQueue = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

function replaceDay(nextDay: TripDay): void {
  if (!itinerary.value) return;
  const index = itinerary.value.days.findIndex((day) => day.id === nextDay.id);
  if (index >= 0) {
    itinerary.value.days[index] = nextDay;
  }
}

function findDay(dayId: string): TripDay | undefined {
  return itinerary.value?.days.find((day) => day.id === dayId);
}

function formatDayTabDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value}T00:00:00`));
}

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError && cause.status === 404) {
    return "这份旅行不存在，或你没有访问权限。";
  }
  if (cause instanceof ApiError && cause.status === 422) {
    return "行程数据不符合规则，请检查日期和时间。";
  }
  return "操作没有完成，请稍后重试。";
}

function clearItineraryDrafts(): void {
  const prefix = "tripmate.itinerary.stop-draft.";
  const keys: string[] = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key?.startsWith(prefix)) keys.push(key);
  }
  for (const key of keys) {
    window.localStorage.removeItem(key);
  }
}

async function captureConflict(
  cause: unknown,
  retry: (expectedVersion: number) => Promise<void>,
  localLabel: string,
  localPayload: unknown,
  draftStopId?: string,
): Promise<void> {
  if (!isVersionConflict(cause) || !auth.token || !tripId.value) return;
  const details = conflictDetails(cause);
  const serverItinerary = await itineraryApi.get(auth.token, tripId.value);
  conflict.value = {
    currentVersion: details.current_version,
    localLabel,
    localPayload,
    serverItinerary,
    retry,
    draftStopId,
  };
  conflictCopyStatus.value = "";
}

async function runVersionedWrite(
  operation: (expectedVersion: number) => Promise<void>,
  localLabel: string,
  localPayload: unknown,
  draftStopId?: string,
): Promise<void> {
  await enqueueWrite(async () => {
    const expectedVersion = itinerary.value?.version;
    if (!expectedVersion) throw new Error("Itinerary version unavailable");
    try {
      await operation(expectedVersion);
    } catch (cause) {
      await captureConflict(
        cause,
        operation,
        localLabel,
        localPayload,
        draftStopId,
      );
      throw cause;
    }
  });
}

async function loadInitial(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  loading.value = true;
  error.value = "";
  try {
    const [loadedTrip, loadedItinerary] = await Promise.all([
      tripApi.get(auth.token, tripId.value),
      itineraryApi.get(auth.token, tripId.value),
    ]);
    trip.value = loadedTrip;
    itinerary.value = loadedItinerary;
  } catch (cause) {
    error.value = errorMessage(cause);
  } finally {
    loading.value = false;
  }
}

async function refreshItinerary(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  refreshing.value = true;
  error.value = "";
  try {
    itinerary.value = await itineraryApi.get(auth.token, tripId.value);
  } catch (cause) {
    error.value = errorMessage(cause);
  } finally {
    refreshing.value = false;
  }
}

async function generateSkeleton(): Promise<void> {
  if (!auth.token || !trip.value || missingDates.value.length === 0) return;
  generating.value = true;
  error.value = "";
  message.value = "";
  try {
    for (const dayDate of missingDates.value) {
      await runVersionedWrite(
        async (expectedVersion) => {
          await itineraryApi.createDay(auth.token!, trip.value!.id, {
            date: dayDate,
            expected_version: expectedVersion,
          });
          itinerary.value!.version = expectedVersion + 1;
        },
        `新增 ${dayDate} 行程日`,
        { date: dayDate },
      );
    }
    await refreshItinerary();
    message.value = "每日行程骨架已生成";
  } catch (cause) {
    if (!isVersionConflict(cause)) error.value = errorMessage(cause);
  } finally {
    generating.value = false;
  }
}

async function addStop(
  dayId: string,
  input: Omit<CreateStopInput, "expected_version">,
): Promise<void> {
  if (!auth.token) return;
  addingDayId.value = dayId;
  addErrors[dayId] = "";
  dayMessages[dayId] = "";
  const label = `新增地点 ${input.place_name || input.place_id}`;
  const operation = async (expectedVersion: number): Promise<void> => {
    const stop = await itineraryApi.createStop(auth.token!, dayId, {
      ...input,
      expected_version: expectedVersion,
    });
    itinerary.value!.version = expectedVersion + 1;
    const day = findDay(dayId);
    if (day) {
      day.stops = [...day.stops, stop].sort(
        (left, right) => left.order_index - right.order_index,
      );
      addResetKeys[dayId] = (addResetKeys[dayId] ?? 0) + 1;
      dayMessages[dayId] = `${stop.place_name || stop.place_id} 已添加`;
    }
  };

  try {
    await runVersionedWrite(operation, label, input);
  } catch (cause) {
    if (!isVersionConflict(cause)) addErrors[dayId] = errorMessage(cause);
  } finally {
    addingDayId.value = null;
  }
}

async function saveStop(
  dayId: string,
  stopId: string,
  input: {
    start_at: string;
    duration_minutes: number;
    estimated_cost_minor: number;
    location: {
      longitude: number;
      latitude: number;
      coordinate_system: "GCJ-02" | "WGS84";
    } | null;
  },
): Promise<void> {
  if (!auth.token) return;
  savingStopId.value = stopId;
  error.value = "";
  dayMessages[dayId] = "";
  const operation = async (expectedVersion: number): Promise<void> => {
    const updated = await itineraryApi.updateStop(auth.token!, stopId, {
      ...input,
      expected_version: expectedVersion,
    });
    itinerary.value!.version = expectedVersion + 1;
    const day = findDay(dayId);
    if (day) {
      day.stops = day.stops.map((stop) => (stop.id === stopId ? updated : stop));
      dayMessages[dayId] = `${updated.place_name || updated.place_id} 已保存`;
    }
  };

  try {
    await runVersionedWrite(
      operation,
      `修改地点 ${findDay(dayId)?.stops.find((stop) => stop.id === stopId)?.place_name || stopId}`,
      { stopId, ...input },
      stopId,
    );
  } catch (cause) {
    if (!isVersionConflict(cause)) error.value = errorMessage(cause);
    throw cause;
  } finally {
    savingStopId.value = null;
  }
}

async function deleteStop(dayId: string, stop: ItineraryStop): Promise<void> {
  if (!auth.token) return;
  const stopName = stop.place_name || stop.place_id;
  if (!window.confirm(`删除 ${stopName}？`)) return;

  const operation = async (expectedVersion: number): Promise<void> => {
    await itineraryApi.deleteStop(auth.token!, stop.id, expectedVersion);
    itinerary.value = await itineraryApi.get(auth.token!, tripId.value);
    dayMessages[dayId] = `${stopName} 已删除`;
  };

  try {
    await runVersionedWrite(operation, `删除地点 ${stopName}`, stop);
  } catch (cause) {
    if (!isVersionConflict(cause)) error.value = errorMessage(cause);
  }
}

async function moveStop(
  dayId: string,
  stopId: string,
  direction: -1 | 1,
): Promise<void> {
  if (!auth.token) return;
  const day = findDay(dayId);
  if (!day) return;

  const currentIndex = day.stops.findIndex((stop) => stop.id === stopId);
  const targetIndex = currentIndex + direction;
  if (currentIndex < 0 || targetIndex < 0 || targetIndex >= day.stops.length) return;

  const stopIds = day.stops.map((stop) => stop.id);
  [stopIds[currentIndex], stopIds[targetIndex]] = [
    stopIds[targetIndex]!,
    stopIds[currentIndex]!,
  ];

  movingStopId.value = stopId;
  error.value = "";
  const operation = async (expectedVersion: number): Promise<void> => {
    const updatedDay = await itineraryApi.reorderStops(
      auth.token!,
      dayId,
      stopIds,
      expectedVersion,
    );
    itinerary.value!.version = expectedVersion + 1;
    replaceDay(updatedDay);
    dayMessages[dayId] = "地点顺序已更新";
  };

  try {
    await runVersionedWrite(operation, "调整地点顺序", stopIds);
  } catch (cause) {
    if (!isVersionConflict(cause)) error.value = errorMessage(cause);
  } finally {
    movingStopId.value = null;
  }
}

async function keepLocal(): Promise<void> {
  const state = conflict.value;
  if (!state) return;
  conflictApplying.value = true;
  try {
    await enqueueWrite(async () => {
      await state.retry(state.currentVersion);
    });
    if (state.draftStopId) {
      draftResetKeys[state.draftStopId] =
        (draftResetKeys[state.draftStopId] ?? 0) + 1;
    }
    conflict.value = null;
    message.value = "已保留本地改动并生成新版本";
  } catch (cause) {
    if (isVersionConflict(cause) && auth.token) {
      const details = conflictDetails(cause);
      conflict.value = {
        ...state,
        currentVersion: details.current_version,
        serverItinerary: await itineraryApi.get(auth.token, tripId.value),
      };
    } else {
      error.value = errorMessage(cause);
    }
  } finally {
    conflictApplying.value = false;
  }
}

function loadServerVersion(): void {
  clearItineraryDrafts();
  window.location.reload();
}

async function copyConflictDiff(): Promise<void> {
  if (!conflict.value) return;
  const text = JSON.stringify(
    {
      localLabel: conflict.value.localLabel,
      local: conflict.value.localPayload,
      server: conflict.value.serverItinerary,
    },
    null,
    2,
  );
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  conflictCopyStatus.value = "已复制";
}

async function openHistory(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  historyOpen.value = true;
  historyLoading.value = true;
  historyError.value = "";
  try {
    history.value = await tripApi.versions(auth.token, tripId.value);
  } catch (cause) {
    historyError.value = errorMessage(cause);
  } finally {
    historyLoading.value = false;
  }
}

async function restoreVersion(version: number): Promise<void> {
  if (!auth.token || !trip.value) return;
  restoringVersion.value = version;
  historyError.value = "";

  const operation = async (expectedVersion: number): Promise<void> => {
    trip.value = await tripApi.restoreVersion(
      auth.token!,
      trip.value!.id,
      version,
      expectedVersion,
    );
    itinerary.value = await itineraryApi.get(auth.token!, trip.value!.id);
    historyOpen.value = false;
    message.value = `已从 v${version} 恢复并生成 v${trip.value.version}`;
    await openHistory();
    historyOpen.value = false;
  };

  try {
    await runVersionedWrite(operation, `恢复版本 v${version}`, { version });
  } catch (cause) {
    if (!isVersionConflict(cause)) historyError.value = errorMessage(cause);
  } finally {
    restoringVersion.value = null;
  }
}

function openReplan(): void {
  replanDayId.value = itinerary.value?.days[0]?.id ?? "";
  replanInstruction.value = "减少一个景点";
  replanError.value = "";
  replanOpen.value = true;
}

async function createReplan(): Promise<void> {
  if (!auth.token || !trip.value || !itinerary.value) return;
  if (!replanDayId.value || !replanInstruction.value.trim()) {
    replanError.value = "请选择行程日并填写调整要求。";
    return;
  }
  replanLoading.value = true;
  replanError.value = "";
  patchError.value = "";
  try {
    patch.value = await patchApi.createReplan(auth.token, trip.value.id, {
      expected_version: itinerary.value.version,
      day_id: replanDayId.value,
      instruction: replanInstruction.value.trim(),
    });
    replanOpen.value = false;
  } catch (cause) {
    replanError.value =
      cause instanceof ApiError && cause.status === 409
        ? "行程已更新，请刷新后重新生成局部重排。"
        : cause instanceof ApiError && cause.status === 422
          ? "当前只支持删除指定数量或名称的地点。"
          : "局部重排没有生成，请稍后重试。";
  } finally {
    replanLoading.value = false;
  }
}

async function applyPatch(): Promise<void> {
  if (!auth.token || !trip.value || !itinerary.value || !patch.value) return;
  patchApplying.value = true;
  patchError.value = "";
  try {
    const result = await patchApi.apply(
      auth.token,
      trip.value.id,
      patch.value.id,
      itinerary.value.version,
    );
    itinerary.value = result.itinerary;
    trip.value.version = result.itinerary.version;
    message.value = `局部重排已应用，生成 v${result.itinerary.version}`;
    patch.value = null;
  } catch (cause) {
    patchError.value =
      cause instanceof ApiError && cause.status === 409
        ? "行程版本已变化，请关闭差异并重新生成。"
        : "调整没有应用，正式行程保持不变。";
  } finally {
    patchApplying.value = false;
  }
}

async function discardPatch(): Promise<void> {
  if (!auth.token || !trip.value || !itinerary.value || !patch.value) return;
  patchApplying.value = true;
  patchError.value = "";
  try {
    await patchApi.discard(
      auth.token,
      trip.value.id,
      patch.value.id,
      itinerary.value.version,
    );
    patch.value = null;
    message.value = "局部重排已丢弃，正式行程未改变";
  } catch {
    patchError.value = "无法丢弃这次调整，请稍后重试。";
  } finally {
    patchApplying.value = false;
  }
}

watch(tripId, loadInitial);
watch(
  () => days.value.map((day) => day.id).join("|"),
  () => {
    if (!days.value.some((day) => day.id === activeDayId.value)) {
      activeDayId.value = days.value[0]?.id ?? "";
    }
  },
  { immediate: true },
);
onMounted(loadInitial);
</script>

<template>
  <main class="itinerary-page">
    <RouterLink class="back-link" :to="`/trips/${tripId}`">
      <ArrowLeft :size="16" :stroke-width="1.8" />
      返回旅行详情
    </RouterLink>

    <div v-if="loading" class="itinerary-loading" aria-label="正在加载逐日行程">
      <span />
      <span />
      <span />
    </div>

    <div v-else-if="!trip || !itinerary" class="trip-state-panel trip-state-panel--error">
      <strong>无法打开逐日行程</strong>
      <span>{{ error }}</span>
      <button class="quiet-action" type="button" @click="loadInitial">
        <RefreshCw :size="16" :stroke-width="1.8" />
        重新加载
      </button>
    </div>

    <template v-else>
      <header class="itinerary-heading">
        <div>
          <p>Trip itinerary</p>
          <h1>逐日行程</h1>
          <div class="itinerary-heading__meta">
            <strong>{{ trip.brief.destination }}</strong>
            <span>
              <CalendarDays :size="14" :stroke-width="1.7" />
              {{ dateRange }}
            </span>
            <span>{{ itinerary.days.length }} 天 · {{ stopCount }} 个地点</span>
            <span>当前版本 v{{ itinerary.version }}</span>
          </div>
        </div>
        <div class="itinerary-heading__actions">
          <RouterLink class="quiet-action" :to="`/trips/${trip.id}/map`">
            <Map :size="16" :stroke-width="1.8" />
            全程路书
          </RouterLink>
          <RouterLink class="quiet-action" :to="`/trips/${trip.id}/budget`">
            <Wallet :size="16" :stroke-width="1.8" />
            预算与支出
          </RouterLink>
          <button class="quiet-action" type="button" @click="openHistory">
            <History :size="16" :stroke-width="1.8" />
            版本历史
          </button>
          <button
            class="quiet-action"
            type="button"
            :disabled="itinerary.days.length === 0"
            @click="openReplan"
          >
            <WandSparkles :size="16" :stroke-width="1.8" />
            局部重排
          </button>
          <button
            class="quiet-action"
            type="button"
            :disabled="refreshing"
            @click="refreshItinerary"
          >
            <RefreshCw
              :size="16"
              :stroke-width="1.8"
              :class="{ 'is-spinning': refreshing }"
            />
            {{ refreshing ? "刷新中" : "刷新" }}
          </button>
          <button
            v-if="missingDates.length"
            class="primary-button"
            type="button"
            :disabled="generating"
            @click="generateSkeleton"
          >
            <Plus :size="16" :stroke-width="1.9" />
            {{ generating ? "生成中" : "生成每日骨架" }}
          </button>
        </div>
      </header>

      <p v-if="message" class="form-success" role="status">{{ message }}</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>

      <div v-if="itinerary.days.length === 0" class="itinerary-empty">
        <span class="itinerary-empty__icon">
          <CalendarDays :size="24" :stroke-width="1.6" />
        </span>
        <h2>还没有逐日行程</h2>
        <p>按 TripBrief 的日期范围生成每日计划，然后逐天添加地点。</p>
        <button
          class="primary-button"
          type="button"
          :disabled="generating"
          @click="generateSkeleton"
        >
          <Plus :size="16" :stroke-width="1.9" />
          {{ generating ? "生成中" : "生成每日骨架" }}
        </button>
      </div>

      <div v-else class="itinerary-day-tabs-shell">
        <div class="itinerary-day-tabs" role="tablist" aria-label="切换行程日期">
          <button
            v-for="day in days"
            :id="`itinerary-tab-${day.id}`"
            :key="day.id"
            class="itinerary-day-tab"
            :class="{ 'is-active': day.id === activeDayId }"
            type="button"
            role="tab"
            :aria-selected="day.id === activeDayId"
            :aria-controls="`itinerary-panel-${day.id}`"
            data-testid="itinerary-day-tab"
            @click="activeDayId = day.id"
          >
            <span class="itinerary-day-tab__number">D{{ day.day_index }}</span>
            <span class="itinerary-day-tab__copy">
              <strong>{{ formatDayTabDate(day.date) }}</strong>
              <small>{{ day.theme || `${day.stops.length} 个地点` }}</small>
            </span>
            <span class="itinerary-day-tab__count">{{ day.stops.length }}</span>
          </button>
        </div>

        <section
          v-if="activeDay"
          :id="`itinerary-panel-${activeDay.id}`"
          class="itinerary-day-panel"
          role="tabpanel"
          :aria-labelledby="`itinerary-tab-${activeDay.id}`"
        >
          <ItineraryDayEditor
            :key="activeDay.id"
            :day="activeDay"
            :auth-token="auth.token ?? ''"
            :city="trip.brief.destination"
            :currency="trip.brief.currency"
            :adding="addingDayId === activeDay.id"
            :add-error="addErrors[activeDay.id] ?? ''"
            :day-message="dayMessages[activeDay.id] ?? ''"
            :reset-key="addResetKeys[activeDay.id] ?? 0"
            :saving-stop-id="savingStopId"
            :moving-stop-id="movingStopId"
            :draft-reset-keys="draftResetKeys"
            :save-stop-handler="saveStop"
            @add-stop="addStop"
            @delete-stop="deleteStop"
            @move-stop="moveStop"
          />
        </section>
      </div>
    </template>

    <VersionConflictDialog
      :open="Boolean(conflict)"
      :current-version="conflict?.currentVersion ?? 0"
      :local-label="conflict?.localLabel ?? ''"
      :copy-status="conflictCopyStatus"
      :applying="conflictApplying"
      @keep-local="keepLocal"
      @load-server="loadServerVersion"
      @copy-diff="copyConflictDiff"
      @close="conflict = null"
    />

    <VersionHistoryDialog
      :open="historyOpen"
      :loading="historyLoading"
      :error="historyError"
      :history="history"
      :restoring-version="restoringVersion"
      @close="historyOpen = false"
      @restore="restoreVersion"
    />

    <Transition name="dialog-fade">
      <div
        v-if="replanOpen"
        class="dialog-backdrop"
        role="presentation"
        @click.self="replanOpen = false"
      >
        <section
          class="replan-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="replan-title"
        >
          <header>
            <div>
              <h2 id="replan-title">局部重排</h2>
            </div>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭局部重排"
              @click="replanOpen = false"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>

          <form @submit.prevent="createReplan">
            <label class="field">
              <span>目标行程日</span>
              <span class="field__control">
                <select v-model="replanDayId" required>
                  <option
                    v-for="day in itinerary?.days ?? []"
                    :key="day.id"
                    :value="day.id"
                  >
                    {{ day.date }} · {{ day.theme || `第 ${day.day_index} 天` }}
                  </option>
                </select>
              </span>
            </label>
            <label class="field">
              <span>调整要求</span>
              <span class="field__control field__control--textarea">
                <textarea
                  v-model="replanInstruction"
                  rows="3"
                  maxlength="2000"
                  required
                  placeholder="例如：减少一个景点"
                />
              </span>
            </label>
            <p v-if="replanError" class="form-error" role="alert">
              {{ replanError }}
            </p>
            <footer>
              <button class="quiet-action" type="button" @click="replanOpen = false">
                取消
              </button>
              <button
                class="primary-button"
                type="submit"
                :disabled="replanLoading"
              >
                <WandSparkles :size="16" :stroke-width="1.8" />
                {{ replanLoading ? "生成中" : "生成差异" }}
              </button>
            </footer>
          </form>
        </section>
      </div>
    </Transition>

    <ItineraryDiff
      :patch="patch"
      :applying="patchApplying"
      :error="patchError"
      @apply="applyPatch"
      @discard="discardPatch"
      @close="patch = null"
    />
  </main>
</template>
