<!-- 文件说明：前端页面：TripsView。 -->
<script setup lang="ts">
import {
  ArrowUpRight,
  CalendarDays,
  MapPin,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  UsersRound,
  X,
} from "lucide-vue-next";
import { onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import LeafActionButton from "../../components/LeafActionButton.vue";
import { tripApi } from "../../features/trips/api";
import type { Trip, TripStatus } from "../../features/trips/types";
import { ApiError } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const trips = ref<Trip[]>([]);
const loading = ref(true);
const error = ref("");
const includeArchived = ref(false);
const pendingDelete = ref<Trip | null>(null);
const deleting = ref(false);
const deleteError = ref("");

const statusLabels: Record<TripStatus, string> = {
  draft: "草稿",
  planning: "规划中",
  ready: "已就绪",
  archived: "已删除",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatRange(trip: Trip): string {
  return `${formatDate(trip.brief.start_date)} - ${formatDate(trip.brief.end_date)}`;
}

async function loadTrips(): Promise<void> {
  if (!auth.token) return;
  loading.value = true;
  error.value = "";
  try {
    trips.value = await tripApi.list(auth.token, includeArchived.value);
  } catch {
    error.value = "旅行列表加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

async function deleteTrip(): Promise<void> {
  if (!auth.token || !pendingDelete.value || deleting.value) return;
  deleting.value = true;
  deleteError.value = "";
  try {
    await tripApi.archive(
      auth.token,
      pendingDelete.value.id,
      pendingDelete.value.version,
    );
    pendingDelete.value = null;
    await loadTrips();
  } catch (cause) {
    deleteError.value =
      cause instanceof ApiError && cause.status === 409
        ? "计划已在其他页面更新，请刷新后再试。"
        : "删除失败，请稍后重试。";
  } finally {
    deleting.value = false;
  }
}

watch(includeArchived, loadTrips);
onMounted(loadTrips);
</script>

<template>
  <main class="trips-page">
    <header class="trips-heading">
      <div>
        <h1>旅行计划</h1>
      </div>
      <div class="trips-heading__actions">
        <button
          class="quiet-action"
          type="button"
          :disabled="loading"
          @click="loadTrips"
        >
          <RefreshCw :size="16" :stroke-width="1.8" :class="{ 'is-spinning': loading }" />
          刷新
        </button>
        <RouterLink class="quiet-action" to="/assistant">
          <Sparkles :size="16" :stroke-width="1.8" />
          AI 解析需求
        </RouterLink>
        <LeafActionButton label="新建旅行" to="/trips/new">
          <template #icon>
            <Plus :size="16" :stroke-width="1.9" />
          </template>
        </LeafActionButton>
      </div>
    </header>

    <div class="trips-toolbar">
      <span>{{ trips.length }} 个{{ includeArchived ? "计划" : "进行中的计划" }}</span>
      <label class="check-control">
        <input v-model="includeArchived" type="checkbox" />
        <span>显示已删除</span>
      </label>
    </div>

    <section class="trip-list-region" aria-live="polite">
      <div v-if="loading" class="trip-list-skeleton" aria-label="正在加载旅行">
        <span v-for="index in 3" :key="index" />
      </div>

      <div v-else-if="error" class="trip-state-panel trip-state-panel--error">
        <strong>列表暂时不可用</strong>
        <span>{{ error }}</span>
        <button class="quiet-action" type="button" @click="loadTrips">重新加载</button>
      </div>

      <div v-else-if="trips.length === 0" class="trip-state-panel">
        <span class="trip-state-panel__icon">
          <MapPin :size="22" :stroke-width="1.6" />
        </span>
        <strong>还没有旅行计划</strong>
        <LeafActionButton label="新建旅行" to="/trips/new">
          <template #icon>
            <Plus :size="16" :stroke-width="1.9" />
          </template>
        </LeafActionButton>
      </div>

      <div v-else class="trip-list">
        <article v-for="trip in trips" :key="trip.id" class="trip-list-row">
          <span class="trip-list-row__rail" aria-hidden="true">
            <MapPin :size="16" :stroke-width="1.8" />
          </span>
          <span class="trip-list-row__route">
            <small>{{ trip.brief.origin || "未设置出发地" }}</small>
            <strong>{{ trip.brief.destination }}</strong>
          </span>
          <span class="trip-list-row__meta">
            <span>
              <CalendarDays :size="14" :stroke-width="1.7" />
              {{ formatRange(trip) }}
            </span>
            <span>
              <UsersRound :size="14" :stroke-width="1.7" />
              {{ trip.brief.party_size }} 人
            </span>
          </span>
          <span class="trip-status" :class="`trip-status--${trip.status}`">
            {{ statusLabels[trip.status] }}
          </span>
          <span class="trip-list-row__actions">
            <button
              v-if="trip.status !== 'archived'"
              class="trip-list-row__delete"
              type="button"
              :aria-label="`删除 ${trip.brief.destination} 旅行计划`"
              @click="pendingDelete = trip"
            >
              <Trash2 :size="15" :stroke-width="1.8" />
            </button>
            <RouterLink
              class="trip-list-row__open"
              :to="`/trips/${trip.id}`"
              :aria-label="`打开 ${trip.brief.destination} 旅行`"
            >
              <ArrowUpRight :size="17" :stroke-width="1.8" />
            </RouterLink>
          </span>
        </article>
      </div>
    </section>

    <Transition name="dialog-fade">
      <div
        v-if="pendingDelete"
        class="dialog-backdrop"
        role="presentation"
        @click.self="pendingDelete = null"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="trip-delete-title"
        >
          <header>
            <h2 id="trip-delete-title">删除这份旅行计划？</h2>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭删除确认"
              @click="pendingDelete = null"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>
          <p>
            {{ pendingDelete.brief.destination }}将从列表移除，历史版本仍保留。
          </p>
          <p v-if="deleteError" class="form-error" role="alert">{{ deleteError }}</p>
          <footer>
            <button class="quiet-action" type="button" @click="pendingDelete = null">
              取消
            </button>
            <button
              class="quiet-action quiet-action--danger"
              type="button"
              :disabled="deleting"
              @click="deleteTrip"
            >
              {{ deleting ? "删除中" : "确认删除" }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
