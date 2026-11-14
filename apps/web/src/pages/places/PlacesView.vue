<!-- 文件说明：前端页面：PlacesView。 -->
<script setup lang="ts">
import {
  Compass,
  ExternalLink,
  Heart,
  Map as MapIcon,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import PlaceMap from "../../features/places/PlaceMap.vue";
import { placeApi } from "../../features/places/api";
import { favoriteApi } from "../../features/share/api";
import type { Favorite } from "../../features/share/types";
import type {
  Place,
  PlaceSearchResponse,
  ProviderStatus,
  SourceFreshness,
} from "../../features/places/types";
import { ApiError } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const form = reactive({
  query: "",
  city: "",
  limit: "10",
});
const providerStatus = ref<ProviderStatus | null>(null);
const response = ref<PlaceSearchResponse | null>(null);
const searching = ref(false);
const loadingStatus = ref(true);
const error = ref("");
const detailLoadingId = ref<string | null>(null);
const details = reactive<Record<string, Place>>({});
const expanded = reactive<Record<string, boolean>>({});
const favorites = ref<Favorite[]>([]);
const favoriteBusyId = ref<string | null>(null);
const selectedPlaceId = ref<string | null>(null);
let searchTimer: number | undefined;
let searchSerial = 0;

const profileLabel = computed(() => {
  if (!providerStatus.value) return "服务状态未知";
  return providerStatus.value.profile === "mock" ? "Mock 数据" : "高德 Web 服务";
});

const favoriteByTarget = computed(
  () => new Map(favorites.value.map((favorite) => [favorite.target_id, favorite])),
);

function freshnessLabel(freshness: SourceFreshness): string {
  return {
    live: "实时",
    cached: "缓存",
    mock: "Mock",
    unknown: "未知",
  }[freshness];
}

function formatQueriedAt(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError && cause.status === 429) {
    return "高德请求已达到配额或频率限制，请稍后重试。";
  }
  if (cause instanceof ApiError && cause.status === 504) {
    return "地图服务响应超时，本次没有返回猜测结果。";
  }
  if (cause instanceof ApiError && cause.status === 503) {
    return "地图服务当前不可用，请检查 Provider 配置。";
  }
  return "地点请求没有完成，请稍后重试。";
}

async function loadStatus(): Promise<void> {
  if (!auth.token) return;
  loadingStatus.value = true;
  try {
    providerStatus.value = await placeApi.status(auth.token);
  } catch (cause) {
    error.value = errorMessage(cause);
  } finally {
    loadingStatus.value = false;
  }
}

async function searchPlaces(auto = false): Promise<void> {
  if (!auth.token || !form.query.trim()) return;
  const serial = ++searchSerial;
  searching.value = true;
  error.value = "";
  try {
    const result = await placeApi.search(auth.token, {
      query: form.query.trim(),
      city: form.city.trim() || undefined,
      limit: Number(form.limit),
    });
    if (serial !== searchSerial) return;
    response.value = result;
    selectedPlaceId.value = result.results[0]?.provider_place_id ?? null;
    for (const key of Object.keys(details)) delete details[key];
    for (const key of Object.keys(expanded)) delete expanded[key];
  } catch (cause) {
    if (serial !== searchSerial) return;
    error.value = errorMessage(cause);
    if (!auto) response.value = null;
  } finally {
    if (serial === searchSerial) searching.value = false;
  }
}

async function toggleDetail(place: Place): Promise<void> {
  if (!auth.token) return;
  expanded[place.provider_place_id] = !expanded[place.provider_place_id];
  if (!expanded[place.provider_place_id] || details[place.provider_place_id]) return;

  detailLoadingId.value = place.provider_place_id;
  error.value = "";
  try {
    details[place.provider_place_id] = await placeApi.get(
      auth.token,
      place.provider_place_id,
    );
  } catch (cause) {
    error.value = errorMessage(cause);
    expanded[place.provider_place_id] = false;
  } finally {
    detailLoadingId.value = null;
  }
}

async function loadFavorites(): Promise<void> {
  if (!auth.token) return;
  try {
    favorites.value = await favoriteApi.list(auth.token, "place");
  } catch {
    // Search remains usable if favorite history is temporarily unavailable.
  }
}

async function toggleFavorite(place: Place): Promise<void> {
  if (!auth.token || favoriteBusyId.value) return;
  favoriteBusyId.value = place.provider_place_id;
  try {
    const existing = favoriteByTarget.value.get(place.provider_place_id);
    if (existing) {
      await favoriteApi.remove(auth.token, existing.id);
      favorites.value = favorites.value.filter((item) => item.id !== existing.id);
    } else {
      const favorite = await favoriteApi.create(auth.token, {
        kind: "place",
        target_id: place.provider_place_id,
        label: place.name,
        details: {
          address: place.address,
          category: place.category,
          location: place.location,
          source: place.source,
        },
      });
      favorites.value = [favorite, ...favorites.value];
    }
  } catch {
    error.value = "收藏操作没有完成，请稍后重试。";
  } finally {
    favoriteBusyId.value = null;
  }
}

watch(
  () => route.query.q,
  (value) => {
    if (typeof value !== "string" || !value.trim()) return;
    form.query = value.trim();
  },
  { immediate: true },
);

watch(
  [() => form.query, () => form.city, () => form.limit],
  () => {
    if (searchTimer !== undefined) window.clearTimeout(searchTimer);
    if (!form.query.trim()) {
      searchSerial += 1;
      response.value = null;
      searching.value = false;
      selectedPlaceId.value = null;
      return;
    }
    searchTimer = window.setTimeout(() => {
      void searchPlaces(true);
    }, 380);
  },
);

onMounted(() => {
  void loadStatus();
  void loadFavorites();
});

onBeforeUnmount(() => {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer);
});
</script>

<template>
  <main class="places-page">
    <header class="places-heading">
      <div>
        <h1>目的地与地点</h1>
      </div>
      <div class="places-provider">
        <span class="provider-dot" :class="{ 'provider-dot--live': providerStatus?.profile === 'live' }" />
        <span>
          <strong>{{ profileLabel }}</strong>
          <small>{{ providerStatus?.configured === false ? "Key 未配置" : "Server-side Provider" }}</small>
        </span>
        <button class="icon-action" type="button" aria-label="刷新 Provider 状态" @click="loadStatus">
          <RefreshCw :size="15" :stroke-width="1.8" :class="{ 'is-spinning': loadingStatus }" />
        </button>
      </div>
    </header>

    <form class="place-search-form" @submit.prevent="searchPlaces(false)">
      <label class="field place-search-form__query">
        <span>搜索地点</span>
        <span class="field__control">
          <Search :size="17" :stroke-width="1.7" />
          <input
            v-model.trim="form.query"
            maxlength="120"
            required
            placeholder="景点、餐厅、地标或地址"
          />
        </span>
      </label>

      <label class="field">
        <span>城市</span>
        <span class="field__control">
          <input v-model.trim="form.city" maxlength="80" placeholder="例如：重庆" />
        </span>
      </label>

      <label class="field place-search-form__limit">
        <span>数量</span>
        <span class="field__control field__control--select">
          <select v-model="form.limit" aria-label="结果数量">
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="20">20</option>
          </select>
        </span>
      </label>

      <button class="primary-button" type="submit" :disabled="searching">
        <Search :size="16" :stroke-width="1.8" />
        {{ searching ? "搜索中" : "搜索" }}
      </button>
    </form>

    <p v-if="error" class="form-error places-error" role="alert">{{ error }}</p>

    <div class="places-workspace">
      <section class="place-results" aria-live="polite">
        <div v-if="searching && !response" class="place-results__skeleton">
          <span v-for="index in 3" :key="index" />
        </div>

        <div v-else-if="!response" class="place-empty">
          <span class="place-empty__icon">
            <Compass :size="23" :stroke-width="1.6" />
          </span>
          <h2>搜索地点</h2>
        </div>

        <div v-else-if="response.results.length === 0" class="place-empty">
          <h2>没有找到匹配地点</h2>
          <p>尝试更换关键词或城市，当前 Provider 没有编造结果。</p>
        </div>

        <template v-else>
          <div class="place-results__meta">
            <span>{{ response.results.length }} 个结果</span>
            <span>{{ searching ? "正在更新" : response.cached ? "来自缓存" : "新查询" }}</span>
            <span>Provider · {{ response.provider }}</span>
          </div>

          <article
            v-for="place in response.results"
            :key="place.provider_place_id"
            class="place-result"
            :class="{ 'is-selected': selectedPlaceId === place.provider_place_id }"
            @click="selectedPlaceId = place.provider_place_id"
          >
          <span class="place-result__pin">
            <MapPin :size="17" :stroke-width="1.8" />
          </span>
          <div class="place-result__main">
            <div class="place-result__title">
              <strong>{{ place.name }}</strong>
              <span>{{ place.category || "未分类" }}</span>
            </div>
            <p>{{ place.address || "地址信息缺失" }}</p>
            <div class="place-result__source">
              <span>{{ freshnessLabel(place.source.freshness) }} · 查询于 {{ formatQueriedAt(place.source.queried_at) }}</span>
              <span v-if="place.location">
                {{ place.location.coordinate_system }} · {{ place.location.longitude.toFixed(6) }},
                {{ place.location.latitude.toFixed(6) }}
              </span>
            </div>

            <div
              v-if="expanded[place.provider_place_id]"
              class="place-result__detail"
            >
              <span v-if="detailLoadingId === place.provider_place_id">正在加载地点详情</span>
              <template v-else-if="details[place.provider_place_id]">
                <span>{{ details[place.provider_place_id]?.address }}</span>
                <span v-if="details[place.provider_place_id]?.tel">
                  电话 · {{ details[place.provider_place_id]?.tel }}
                </span>
                <a
                  v-if="details[place.provider_place_id]?.source.source_url"
                  :href="details[place.provider_place_id]?.source.source_url || undefined"
                  target="_blank"
                  rel="noreferrer"
                >
                  查看供应商来源
                  <ExternalLink :size="12" :stroke-width="1.8" />
                </a>
              </template>
            </div>
          </div>
          <div class="place-result__actions">
            <button
              class="icon-action"
              :class="{ 'is-favorite': favoriteByTarget.has(place.provider_place_id) }"
              type="button"
              :aria-label="
                favoriteByTarget.has(place.provider_place_id)
                  ? `取消收藏 ${place.name}`
                  : `收藏 ${place.name}`
              "
              :disabled="favoriteBusyId === place.provider_place_id"
              @click="toggleFavorite(place)"
            >
              <Heart
                :size="16"
                :stroke-width="1.8"
                :fill="
                  favoriteByTarget.has(place.provider_place_id)
                    ? 'currentColor'
                    : 'none'
                "
              />
            </button>
            <button
              class="quiet-action place-result__detail-button"
              type="button"
              :aria-label="`查看 ${place.name} 详情`"
              @click="toggleDetail(place)"
            >
              {{ expanded[place.provider_place_id] ? "收起" : "详情" }}
            </button>
          </div>
          </article>
        </template>
      </section>

      <aside class="places-map-panel" aria-label="地点地图">
        <header>
          <MapIcon :size="16" :stroke-width="1.8" />
          <strong>地图</strong>
          <span>{{ response?.results.length ?? 0 }} 个结果</span>
        </header>
        <PlaceMap
          :places="response?.results ?? []"
          :selected-id="selectedPlaceId"
          @select="selectedPlaceId = $event.provider_place_id"
        />
      </aside>
    </div>
  </main>
</template>
