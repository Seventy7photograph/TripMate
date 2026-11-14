<!-- 文件说明：前端页面：TripDetailView。 -->
<script setup lang="ts">
import {
  ArrowLeft,
  Bot,
  CalendarDays,
  CalendarRange,
  Download,
  Heart,
  HeartOff,
  Link2,
  Printer,
  RefreshCw,
  Share2,
  Trash2,
  UsersRound,
  Wallet,
  X,
} from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { tripApi } from "../../features/trips/api";
import { itineraryApi } from "../../features/itinerary/api";
import { favoriteApi, shareApi } from "../../features/share/api";
import { exportTripImage, printTripPdf } from "../../features/share/export";
import type {
  Favorite,
  ShareCreateResult,
  ShareSummary,
} from "../../features/share/types";
import TripBriefEditor from "../../features/trips/TripBriefEditor.vue";
import type { Trip, TripBrief, TripStatus } from "../../features/trips/types";
import { ApiError } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const trip = ref<Trip | null>(null);
const loading = ref(true);
const submitting = ref(false);
const archiving = ref(false);
const itineraryDayCount = ref<number | null>(null);
const deleteOpen = ref(false);
const error = ref("");
const message = ref("");
const selectedStatus = ref<TripStatus>("draft");
const tripFavorite = ref<Favorite | null>(null);
const favoriteBusy = ref(false);
const shares = ref<ShareSummary[]>([]);
const sharePanelOpen = ref(false);
const shareExpiry = ref(30);
const shareCreating = ref(false);
const shareError = ref("");
const shareMessage = ref("");
const latestShare = ref<ShareCreateResult | null>(null);
const exporting = ref<"image" | "pdf" | null>(null);

const statusLabels: Record<TripStatus, string> = {
  draft: "草稿",
  planning: "规划中",
  ready: "已就绪",
  archived: "已删除",
};

const paceLabels = {
  relaxed: "轻松",
  balanced: "均衡",
  intensive: "紧凑",
} as const;

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
  const start = formatter.format(new Date(`${trip.value.brief.start_date}T00:00:00`));
  const end = formatter.format(new Date(`${trip.value.brief.end_date}T00:00:00`));
  return `${start} - ${end}`;
});

const budgetLabel = computed(() => {
  if (!trip.value || trip.value.brief.budget_minor === null) return "未设置";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: trip.value.brief.currency,
    maximumFractionDigits: 0,
  }).format(trip.value.brief.budget_minor / 100);
});

function applyTrip(nextTrip: Trip): void {
  trip.value = nextTrip;
  selectedStatus.value = nextTrip.status;
}

async function loadTrip(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  loading.value = true;
  error.value = "";
  try {
    applyTrip(await tripApi.get(auth.token, tripId.value));
    await loadTripExtras();
  } catch (cause) {
    error.value =
      cause instanceof ApiError && cause.status === 404
        ? "这份旅行不存在，或你没有访问权限。"
        : "旅行加载失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

async function loadTripExtras(): Promise<void> {
  if (!auth.token || !trip.value) return;
  try {
    const [favorites, shareItems, itinerary] = await Promise.all([
      favoriteApi.list(auth.token, "trip"),
      shareApi.list(auth.token, trip.value.id),
      itineraryApi.get(auth.token, trip.value.id).catch(() => null),
    ]);
    tripFavorite.value =
      favorites.find((favorite) => favorite.target_id === trip.value?.id) ?? null;
    shares.value = shareItems;
    itineraryDayCount.value = itinerary?.days.length ?? 0;
  } catch {
    // Sharing and favorites are secondary to opening the trip.
  }
}

async function toggleTripFavorite(): Promise<void> {
  if (!auth.token || !trip.value || favoriteBusy.value) return;
  favoriteBusy.value = true;
  try {
    if (tripFavorite.value) {
      await favoriteApi.remove(auth.token, tripFavorite.value.id);
      tripFavorite.value = null;
    } else {
      tripFavorite.value = await favoriteApi.create(auth.token, {
        kind: "trip",
        target_id: trip.value.id,
        label: trip.value.brief.destination,
        details: {
          start_date: trip.value.brief.start_date,
          end_date: trip.value.brief.end_date,
        },
      });
    }
  } catch {
    error.value = "旅行收藏操作失败，请稍后重试。";
  } finally {
    favoriteBusy.value = false;
  }
}

async function createShare(): Promise<void> {
  if (!auth.token || !trip.value || shareCreating.value) return;
  shareCreating.value = true;
  shareError.value = "";
  shareMessage.value = "";
  try {
    latestShare.value = await shareApi.create(
      auth.token,
      trip.value.id,
      shareExpiry.value,
    );
    await copyShare(latestShare.value);
    await loadTripExtras();
  } catch {
    shareError.value = "分享链接创建失败，请稍后重试。";
  } finally {
    shareCreating.value = false;
  }
}

async function copyShare(share: ShareCreateResult): Promise<void> {
  const url = `${window.location.origin}${share.url_path}`;
  try {
    await navigator.clipboard.writeText(url);
    shareMessage.value = "分享链接已复制";
  } catch {
    shareMessage.value = url;
  }
}

async function revokeShare(shareId: string): Promise<void> {
  if (!auth.token) return;
  try {
    await shareApi.revoke(auth.token, shareId);
    shares.value = await shareApi.list(auth.token, tripId.value);
    if (latestShare.value?.id === shareId) latestShare.value = null;
    shareMessage.value = "分享已撤销";
  } catch {
    shareError.value = "撤销分享失败，请稍后重试。";
  }
}

async function exportTrip(kind: "image" | "pdf"): Promise<void> {
  if (!auth.token || !trip.value || exporting.value) return;
  exporting.value = kind;
  error.value = "";
  try {
    const document = await shareApi.exportDocument(auth.token, trip.value.id);
    if (kind === "image") {
      await exportTripImage(document, document.filename);
    } else {
      printTripPdf(document);
    }
  } catch {
    error.value = "导出失败，请稍后重试。";
  } finally {
    exporting.value = null;
  }
}

async function saveBrief(brief: TripBrief): Promise<void> {
  if (!auth.token || !trip.value) return;
  submitting.value = true;
  error.value = "";
  message.value = "";
  try {
    applyTrip(
      await tripApi.update(auth.token, trip.value.id, {
        expected_version: trip.value.version,
        brief,
      }),
    );
    message.value = "旅行需求已保存";
  } catch (cause) {
    error.value =
      cause instanceof ApiError && cause.status === 422
        ? "请检查日期、人数、预算和必填字段。"
        : "保存失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}

async function saveStatus(): Promise<void> {
  if (!auth.token || !trip.value || selectedStatus.value === trip.value.status) return;
  message.value = "";
  error.value = "";
  try {
    applyTrip(
      await tripApi.update(auth.token, trip.value.id, {
        expected_version: trip.value.version,
        status: selectedStatus.value,
      }),
    );
    message.value = "旅行状态已更新";
  } catch {
    selectedStatus.value = trip.value.status;
    error.value = "状态更新失败，请稍后重试。";
  }
}

async function archiveTrip(): Promise<void> {
  if (!auth.token || !trip.value) return;

  archiving.value = true;
  error.value = "";
  try {
    await tripApi.archive(auth.token, trip.value.id, trip.value.version);
    await router.push("/trips");
  } catch {
    error.value = "删除失败，请稍后重试。";
    archiving.value = false;
  }
}

watch(tripId, loadTrip);
onMounted(loadTrip);
</script>

<template>
  <main class="trip-detail-page">
    <RouterLink class="back-link" to="/trips">
      <ArrowLeft :size="16" :stroke-width="1.8" />
      返回旅行列表
    </RouterLink>

    <div v-if="loading" class="trip-detail-loading" aria-label="正在加载旅行">
      <span />
      <span />
      <span />
    </div>

    <div v-else-if="!trip" class="trip-state-panel trip-state-panel--error">
      <strong>无法打开旅行</strong>
      <span>{{ error }}</span>
      <button class="quiet-action" type="button" @click="loadTrip">
        <RefreshCw :size="16" :stroke-width="1.8" />
        重新加载
      </button>
    </div>

    <template v-else>
      <header class="trip-detail-heading">
        <div>
          <h1>{{ trip.brief.destination }}</h1>
          <div class="trip-detail-meta">
            <span>{{ trip.brief.origin || "未设置出发地" }}</span>
            <span>
              <CalendarDays :size="14" :stroke-width="1.7" />
              {{ dateRange }}
            </span>
            <span>
              <UsersRound :size="14" :stroke-width="1.7" />
              {{ trip.brief.party_size }} 人
            </span>
          </div>
        </div>
        <div class="trip-detail-heading__aside">
          <span class="trip-status" :class="`trip-status--${trip.status}`">
            {{ statusLabels[trip.status] }}
          </span>
          <span class="version-chip">版本 {{ trip.version }}</span>
          <button
            class="quiet-action"
            type="button"
            :disabled="favoriteBusy"
            @click="toggleTripFavorite"
          >
            <HeartOff v-if="tripFavorite" :size="16" :stroke-width="1.8" />
            <Heart v-else :size="16" :stroke-width="1.8" />
            {{ tripFavorite ? "取消收藏" : "收藏" }}
          </button>
          <button
            class="quiet-action quiet-action--danger"
            type="button"
            :disabled="archiving || trip.status === 'archived'"
            @click="deleteOpen = true"
          >
            <Trash2 :size="16" :stroke-width="1.8" />
            {{ trip.status === "archived" ? "已删除" : "删除计划" }}
          </button>
        </div>
      </header>

      <p v-if="message" class="form-success" role="status">{{ message }}</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>

      <div class="trip-detail-layout">
        <aside class="trip-summary" aria-label="旅行摘要">
          <section>
            <span class="trip-summary__label">当前状态</span>
            <span class="field__control">
              <select v-model="selectedStatus" @change="saveStatus">
                <option value="draft">草稿</option>
                <option value="planning">规划中</option>
                <option value="ready">已就绪</option>
                <option value="archived">已删除</option>
              </select>
            </span>
          </section>

          <dl class="trip-summary__facts">
            <div>
              <dt>预算</dt>
              <dd>{{ budgetLabel }}</dd>
            </div>
            <div>
              <dt>节奏</dt>
              <dd>{{ paceLabels[trip.brief.pace] }}</dd>
            </div>
            <div>
              <dt>兴趣</dt>
              <dd>{{ trip.brief.interests.join(" · ") || "未设置" }}</dd>
            </div>
            <div>
              <dt>约束</dt>
              <dd>{{ trip.brief.constraints.join(" · ") || "未设置" }}</dd>
            </div>
          </dl>

          <section class="trip-share-panel">
            <button
              class="quiet-action trip-share-panel__toggle"
              type="button"
              @click="sharePanelOpen = !sharePanelOpen"
            >
              <Share2 :size="16" :stroke-width="1.8" />
              {{ sharePanelOpen ? "收起分享设置" : "分享与导出" }}
            </button>
            <div v-if="sharePanelOpen" class="trip-share-panel__body">
              <div class="trip-share-panel__create">
                <label class="field">
                  <span>链接有效期</span>
                  <span class="field__control">
                    <select v-model.number="shareExpiry">
                      <option :value="7">7 天</option>
                      <option :value="30">30 天</option>
                      <option :value="90">90 天</option>
                    </select>
                  </span>
                </label>
                <button
                  class="primary-button"
                  type="button"
                  :disabled="shareCreating"
                  @click="createShare"
                >
                  <Link2 :size="15" :stroke-width="1.8" />
                  {{ shareCreating ? "创建中" : "创建分享链接" }}
                </button>
              </div>
              <p v-if="shareError" class="form-error" role="alert">{{ shareError }}</p>
              <p v-if="shareMessage" class="form-success" role="status">{{ shareMessage }}</p>
              <div v-if="shares.length" class="trip-share-links">
                <article v-for="item in shares" :key="item.id">
                  <span>
                    <strong>v{{ trip.version }} 只读链接</strong>
                    <small>
                      {{ item.status }} · 有效至
                      {{ new Date(item.expires_at).toLocaleDateString("zh-CN") }}
                    </small>
                  </span>
                  <button
                    v-if="item.status === 'active'"
                    class="icon-action icon-action--danger"
                    type="button"
                    aria-label="撤销分享链接"
                    @click="revokeShare(item.id)"
                  >
                    <Trash2 :size="15" :stroke-width="1.8" />
                  </button>
                </article>
              </div>
              <div class="trip-export-actions">
                <button
                  class="quiet-action"
                  type="button"
                  :disabled="Boolean(exporting)"
                  @click="exportTrip('image')"
                >
                  <Download :size="15" :stroke-width="1.8" />
                  {{ exporting === "image" ? "导出中" : "导出图片" }}
                </button>
                <button
                  class="quiet-action"
                  type="button"
                  :disabled="Boolean(exporting)"
                  @click="exportTrip('pdf')"
                >
                  <Printer :size="15" :stroke-width="1.8" />
                  {{ exporting === "pdf" ? "准备中" : "打印 / PDF" }}
                </button>
              </div>
            </div>
          </section>

          <RouterLink
            class="primary-button trip-summary__itinerary-link"
            :to="`/trips/${trip.id}/itinerary`"
          >
            <CalendarRange :size="16" :stroke-width="1.8" />
            编辑逐日行程
          </RouterLink>
          <RouterLink
            class="quiet-action trip-summary__itinerary-link"
            :to="`/trips/${trip.id}/budget`"
          >
            <Wallet :size="16" :stroke-width="1.8" />
            预算与支出
          </RouterLink>
          <RouterLink
            v-if="itineraryDayCount === 0"
            class="quiet-action trip-summary__itinerary-link"
            :to="`/trips/${trip.id}/plan`"
          >
            <Bot :size="16" :stroke-width="1.8" />
            生成 AI 行程
          </RouterLink>
        </aside>

        <section class="trip-detail-editor" aria-labelledby="trip-editor-title">
          <header>
            <h2 id="trip-editor-title">旅行需求</h2>
          </header>
          <TripBriefEditor
            :initial-value="trip.brief"
            submit-label="保存旅行"
            :submitting="submitting"
            @submit="saveBrief"
          />
        </section>
      </div>
    </template>

    <Transition name="dialog-fade">
      <div
        v-if="deleteOpen && trip"
        class="dialog-backdrop"
        role="presentation"
        @click.self="deleteOpen = false"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="trip-detail-delete-title"
        >
          <header>
            <h2 id="trip-detail-delete-title">删除这份旅行计划？</h2>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭删除确认"
              @click="deleteOpen = false"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>
          <p>{{ trip.brief.destination }}将从列表移除，历史版本仍保留。</p>
          <footer>
            <button class="quiet-action" type="button" @click="deleteOpen = false">
              取消
            </button>
            <button
              class="quiet-action quiet-action--danger"
              type="button"
              :disabled="archiving"
              @click="archiveTrip"
            >
              {{ archiving ? "删除中" : "确认删除" }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
