<!-- 文件说明：前端页面：map。 -->
<script setup lang="ts">
import {
  ArrowLeft,
  Clock3,
  ChevronDown,
  ChevronUp,
  Edit3,
  Expand,
  GripVertical,
  MapPin,
  Navigation,
  Plus,
  RefreshCw,
  Route,
  TriangleAlert,
  Trash2,
} from "lucide-vue-next";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import MapCanvas from "../../../components/MapCanvas.vue";
import { itineraryApi } from "../../../features/itinerary/api";
import {
  dateTimeFor,
  parseAmountToMinor,
  timeFromDateTime,
} from "../../../features/itinerary/form";
import type {
  CreateStopInput,
  Itinerary,
  ItineraryStop,
  RouteMode,
  StopLocation,
  TripDay,
} from "../../../features/itinerary/types";
import { routeApi } from "../../../features/map/api";
import {
  createFlightArcLeg,
  buildRouteSegments,
  distanceBetweenLocations,
  formatDistance,
  formatDuration,
} from "../../../features/map/form";
import type { RouteLeg, RouteLegError } from "../../../features/map/types";
import { selectRouteBookDay } from "../../../features/map/routeBook";
import PlacePicker from "../../../features/places/PlacePicker.vue";
import { placeApi } from "../../../features/places/api";
import type { Place } from "../../../features/places/types";
import { tripApi } from "../../../features/trips/api";
import type { Trip } from "../../../features/trips/types";
import { useAuthStore } from "../../../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const trip = ref<Trip | null>(null);
const itinerary = ref<Itinerary | null>(null);
const day = ref<TripDay | null>(null);
const legs = ref<RouteLeg[]>([]);
const allLegs = ref<RouteLeg[]>([]);
const routeErrors = ref<RouteLegError[]>([]);
const mapCenter = ref<StopLocation | null>(null);
const loading = ref(true);
const calculating = ref(false);
const error = ref("");
const routeError = ref("");
const zoom = ref(14);
const mapShell = ref<HTMLElement | null>(null);
const legModes = ref<RouteMode[]>([]);
const routeCache = new Map<
  string,
  { legs: RouteLeg[]; modes: RouteMode[]; errors: RouteLegError[] }
>();
const stopEditorOpen = ref(false);
const editingStopId = ref<string | null>(null);
const stopSaving = ref(false);
const stopEditorError = ref("");
const draggingStopId = ref<string | null>(null);
const stopForm = reactive({
  placeName: "",
  placeId: "",
  time: "09:00",
  duration: "90",
  cost: "",
  longitude: "",
  latitude: "",
  coordinateSystem: "GCJ-02" as "GCJ-02" | "WGS84",
  source: null as ItineraryStop["source"] | null,
});

const tripId = computed(() =>
  typeof route.params.tripId === "string" ? route.params.tripId : "",
);
const dayId = computed(() =>
  typeof route.params.dayId === "string" ? route.params.dayId : "",
);
const days = computed(() => itinerary.value?.days ?? []);
const allStops = computed(() => days.value.flatMap((item) => item.stops));
const displayStops = computed(() => day.value?.stops ?? allStops.value);
const displayLegs = computed(() => (day.value ? legs.value : allLegs.value));
const segments = computed(() =>
  day.value
    ? buildRouteSegments(day.value.stops, legs.value, routeErrors.value)
    : [],
);
const dateRange = computed(() =>
  trip.value
    ? `${trip.value.brief.start_date.slice(5).replace("-", ".")} — ${trip.value.brief.end_date.slice(5).replace("-", ".")}`
    : "",
);

const modeLabels: Record<RouteMode, string> = {
  driving: "驾车",
  walking: "步行",
  bicycling: "骑行",
  transit: "公交",
  bus: "公交",
  subway: "地铁",
  high_speed_rail: "高铁",
  train: "火车",
  flight: "飞机",
};
const modeLimits: Partial<Record<RouteMode, number>> = {
  walking: 100_000,
  bicycling: 500_000,
};
const modeWarning = ref<{
  index: number;
  previous: RouteMode;
  selected: RouteMode;
  distance: number;
} | null>(null);

async function loadPage(): Promise<void> {
  if (!auth.token || !tripId.value) return;
  loading.value = true;
  error.value = "";
  legs.value = [];
  allLegs.value = [];
  routeErrors.value = [];
  mapCenter.value = null;
  routeError.value = "";
  try {
    const [loadedTrip, loadedItinerary] = await Promise.all([
      tripApi.get(auth.token, tripId.value),
      itineraryApi.get(auth.token, tripId.value),
    ]);
    const loadedDay = selectRouteBookDay(loadedItinerary.days, dayId.value);
    if (dayId.value && !loadedDay) throw new Error("Trip day not found");
    trip.value = loadedTrip;
    itinerary.value = loadedItinerary;
    day.value = loadedDay;
    if (loadedDay) {
      const cached = routeCache.get(loadedDay.id);
      legs.value = cached?.legs ?? [];
      legModes.value =
        cached?.modes ??
        (loadedDay.leg_modes.length ===
        Math.max(loadedDay.stops.length - 1, 0)
          ? loadedDay.leg_modes
          : defaultModes(loadedDay.stops.length));
    } else {
      legs.value = [];
      legModes.value = [];
    }
    await ensureMapCenter(loadedTrip, loadedItinerary);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "地图页面加载失败";
  } finally {
    loading.value = false;
  }
  if (trip.value && itinerary.value) {
    await calculateAllRoutes();
    syncRouteDisplay();
  }
}

async function ensureMapCenter(
  loadedTrip: Trip,
  loadedItinerary: Itinerary,
): Promise<void> {
  if (!auth.token) return;
  const hasLocatedStop = loadedItinerary.days.some((item) =>
    item.stops.some((stop) => stop.location),
  );
  if (hasLocatedStop) return;
  const city = loadedTrip.brief.origin?.trim() || loadedTrip.brief.destination;
  try {
    mapCenter.value = await placeApi.geocode(auth.token, city);
  } catch {
    routeError.value = "出发城市坐标获取失败，地图将显示全国范围。";
  }
}

function defaultModes(stopCount: number): RouteMode[] {
  return Array.from(
    { length: Math.max(stopCount - 1, 0) },
    () => "walking" as RouteMode,
  );
}

function syncRouteDisplay(): void {
  allLegs.value = days.value.flatMap(
    (item) => routeCache.get(item.id)?.legs ?? [],
  );
  if (!day.value) {
    legs.value = [];
    legModes.value = [];
    return;
  }
  const cached = routeCache.get(day.value.id);
  legs.value = cached?.legs ?? [];
  routeErrors.value = cached?.errors ?? [];
  legModes.value = cached?.modes ?? defaultModes(day.value.stops.length);
}

async function calculateAllRoutes(
  force = false,
  modeOverride?: { dayId: string; modes: RouteMode[] },
): Promise<void> {
  if (!auth.token || !itinerary.value) return;
  calculating.value = true;
  routeError.value = "";
  error.value = "";
  const failures: string[] = [];
  try {
    for (const item of days.value) {
      const cached = routeCache.get(item.id);
      const locatedCount = item.stops.filter((stop) => stop.location).length;
      const modes =
        modeOverride?.dayId === item.id
          ? [...modeOverride.modes]
          : cached?.modes.length === Math.max(item.stops.length - 1, 0)
          ? [...cached.modes]
          : item.leg_modes.length === Math.max(item.stops.length - 1, 0)
            ? [...item.leg_modes]
          : defaultModes(item.stops.length);
      if (locatedCount < 2) {
        routeCache.set(item.id, { legs: [], modes, errors: [] });
        continue;
      }
      if (!force && cached?.legs.length) continue;
      try {
        const result = await routeApi.calculate(
          auth.token,
          tripId.value,
          item.id,
          {
            expected_version: itinerary.value.version,
            stop_ids: item.stops.map((stop) => stop.id),
            mode: modes[0] ?? "walking",
            modes,
          },
        );
        const flightLegs = item.stops.flatMap((stop, index) => {
          const next = item.stops[index + 1];
          if (!next || modes[index] !== "flight") return [];
          const leg = createFlightArcLeg(stop, next);
          return leg ? [leg] : [];
        });
        const providerLegs = result.legs.filter((leg) => leg.mode !== "flight");
        const providerErrors = result.errors.filter(
          (routeError) => routeError.mode !== "flight",
        );
        const nextLegs = [...providerLegs, ...flightLegs];
        routeCache.set(item.id, {
          legs: nextLegs,
          modes: result.modes,
          errors: providerErrors,
        });
        item.leg_modes = result.modes;
        if (!nextLegs.length) failures.push(`第 ${item.day_index} 天无可用路线`);
        if (providerErrors.length) {
          failures.push(
            ...providerErrors.map(
              (routeError) =>
                `第 ${item.day_index} 天 ${modeLabels[routeError.mode]}：${friendlyRouteError(routeError)}`,
            ),
          );
        }
      } catch (cause) {
        failures.push(
          `第 ${item.day_index} 天：${
            cause instanceof Error ? cause.message : "路线计算失败"
          }`,
        );
        routeCache.set(item.id, { legs: [], modes, errors: [] });
      }
    }
    syncRouteDisplay();
    if (failures.length) {
      routeError.value = failures.join("；");
    }
  } finally {
    calculating.value = false;
  }
}

function friendlyRouteError(error: RouteLegError): string {
  if (
    error.code === "provider_response_invalid" &&
    (error.mode === "walking" || error.mode === "bicycling")
  ) {
    return `${modeLabels[error.mode]}距离超过 Provider 限制，请切换交通方式`;
  }
  if (error.code === "provider_timeout") return "路线服务超时，请稍后重试";
  return error.message;
}

function handleModeChange(index: number, event: Event): void {
  const select = event.target as HTMLSelectElement;
  const selected = select.value as RouteMode;
  const previous = legModes.value[index] ?? "walking";
  const from = day.value?.stops[index];
  const to = day.value?.stops[index + 1];
  const limit = modeLimits[selected];
  if (from?.location && to?.location && limit !== undefined) {
    const distance = distanceBetweenLocations(from.location, to.location);
    if (distance > limit) {
      select.value = previous;
      modeWarning.value = { index, previous, selected, distance };
      return;
    }
  }
  legModes.value[index] = selected;
  void calculateCurrentRoute();
}

async function acceptModeWarning(): Promise<void> {
  const warning = modeWarning.value;
  if (!warning) return;
  legModes.value[warning.index] = warning.selected;
  modeWarning.value = null;
  await calculateCurrentRoute();
}

async function switchWarningToDriving(): Promise<void> {
  const warning = modeWarning.value;
  if (!warning) return;
  legModes.value[warning.index] = "driving";
  modeWarning.value = null;
  await calculateCurrentRoute();
}

async function calculateCurrentRoute(): Promise<void> {
  if (!day.value) return;
  routeCache.delete(day.value.id);
  await calculateAllRoutes(false, {
    dayId: day.value.id,
    modes: [...legModes.value],
  });
}

function invalidateRoute(dayId = day.value?.id): void {
  if (dayId) routeCache.delete(dayId);
  legs.value = [];
  allLegs.value = [];
  routeErrors.value = [];
}

function suggestedStopTime(): string {
  const lastStop = day.value?.stops.at(-1);
  if (!lastStop) return "09:00";
  const [hours = "0", minutes = "0"] = lastStop.start_at.slice(11, 16).split(":");
  const total = Number(hours) * 60 + Number(minutes) + lastStop.duration_minutes;
  return `${String(Math.floor(total / 60) % 24).padStart(2, "0")}:${String(
    total % 60,
  ).padStart(2, "0")}`;
}

function resetStopForm(): void {
  stopForm.placeName = "";
  stopForm.placeId = "";
  stopForm.time = suggestedStopTime();
  stopForm.duration = "90";
  stopForm.cost = "";
  stopForm.longitude = "";
  stopForm.latitude = "";
  stopForm.coordinateSystem = "GCJ-02";
  stopForm.source = null;
  stopEditorError.value = "";
}

function openAddStop(): void {
  editingStopId.value = null;
  resetStopForm();
  stopEditorOpen.value = true;
}

function openEditStop(stop: ItineraryStop): void {
  editingStopId.value = stop.id;
  stopForm.placeName = stop.place_name || stop.place_id;
  stopForm.placeId = stop.place_id;
  stopForm.time = timeFromDateTime(stop.start_at);
  stopForm.duration = String(stop.duration_minutes);
  stopForm.cost = (stop.estimated_cost_minor / 100).toFixed(2).replace(/\.00$/, "");
  stopForm.longitude = stop.location ? String(stop.location.longitude) : "";
  stopForm.latitude = stop.location ? String(stop.location.latitude) : "";
  stopForm.coordinateSystem = stop.location?.coordinate_system ?? "GCJ-02";
  stopForm.source = stop.source;
  stopEditorError.value = "";
  stopEditorOpen.value = true;
}

function selectStopPlace(place: Place): void {
  stopForm.placeName = place.name;
  stopForm.placeId = place.provider_place_id;
  stopForm.longitude = place.location ? String(place.location.longitude) : "";
  stopForm.latitude = place.location ? String(place.location.latitude) : "";
  stopForm.coordinateSystem = place.location?.coordinate_system ?? "GCJ-02";
  stopForm.source = place.source;
  stopEditorError.value = "";
}

function stopLocation() {
  if (!stopForm.longitude.trim() && !stopForm.latitude.trim()) return null;
  return {
    longitude: Number(stopForm.longitude),
    latitude: Number(stopForm.latitude),
    coordinate_system: stopForm.coordinateSystem,
  };
}

async function saveStop(): Promise<void> {
  if (!auth.token || !day.value || !itinerary.value) return;
  const name = stopForm.placeName.trim();
  const duration = Number(stopForm.duration);
  const cost = parseAmountToMinor(stopForm.cost);
  const location = stopLocation();
  if (!name || !/^\d{2}:\d{2}$/.test(stopForm.time)) {
    stopEditorError.value = "请填写地点和开始时间。";
    return;
  }
  if (!Number.isInteger(duration) || duration < 1 || duration > 1440) {
    stopEditorError.value = "停留时间需为 1 到 1440 分钟。";
    return;
  }
  if (cost === undefined || (location && (
    !Number.isFinite(location.longitude) ||
    !Number.isFinite(location.latitude) ||
    Math.abs(location.longitude) > 180 ||
    Math.abs(location.latitude) > 90
  ))) {
    stopEditorError.value = "地点坐标或金额格式不正确。";
    return;
  }

  stopSaving.value = true;
  stopEditorError.value = "";
  try {
    const common = {
      place_id: stopForm.placeId || `manual-${crypto.randomUUID()}`,
      place_name: name,
      start_at: dateTimeFor(day.value.date, stopForm.time),
      duration_minutes: duration,
      estimated_cost_minor: cost ?? 0,
      location,
      source: stopForm.source,
    } satisfies Omit<CreateStopInput, "expected_version">;
    if (editingStopId.value) {
      await itineraryApi.updateStop(auth.token, editingStopId.value, {
        expected_version: itinerary.value.version,
        ...common,
      });
    } else {
      await itineraryApi.createStop(auth.token, day.value.id, {
        expected_version: itinerary.value.version,
        ...common,
      });
    }
    stopEditorOpen.value = false;
    invalidateRoute();
    await loadPage();
  } catch {
    stopEditorError.value = "地点没有保存，请检查后重试。";
  } finally {
    stopSaving.value = false;
  }
}

async function deleteStop(stop: ItineraryStop): Promise<void> {
  if (!auth.token || !itinerary.value) return;
  if (!window.confirm(`删除 ${stop.place_name || stop.place_id}？`)) return;
  try {
    await itineraryApi.deleteStop(auth.token, stop.id, itinerary.value.version);
    invalidateRoute();
    await loadPage();
  } catch {
    routeError.value = "地点删除失败，请稍后重试。";
  }
}

async function reorderStops(nextStops: ItineraryStop[]): Promise<void> {
  if (!auth.token || !day.value || !itinerary.value) return;
  try {
    const updatedDay = await itineraryApi.reorderStops(
      auth.token,
      day.value.id,
      nextStops.map((stop) => stop.id),
      itinerary.value.version,
    );
    day.value = updatedDay;
    itinerary.value.version += 1;
    itinerary.value.days = itinerary.value.days.map((item) =>
      item.id === updatedDay.id ? updatedDay : item,
    );
    legModes.value = Array.from(
      { length: Math.max(updatedDay.stops.length - 1, 0) },
      (_, index) => legModes.value[index] ?? "walking",
    );
    invalidateRoute();
  } catch {
    routeError.value = "地点顺序没有保存，请稍后重试。";
  }
}

async function moveStop(index: number, direction: -1 | 1): Promise<void> {
  if (!day.value) return;
  const target = index + direction;
  if (target < 0 || target >= day.value.stops.length) return;
  const next = [...day.value.stops];
  [next[index], next[target]] = [next[target]!, next[index]!];
  await reorderStops(next);
}

async function dropStop(targetId: string): Promise<void> {
  if (!day.value || !draggingStopId.value || draggingStopId.value === targetId) {
    draggingStopId.value = null;
    return;
  }
  const next = [...day.value.stops];
  const sourceIndex = next.findIndex((stop) => stop.id === draggingStopId.value);
  const targetIndex = next.findIndex((stop) => stop.id === targetId);
  if (sourceIndex < 0 || targetIndex < 0) return;
  const [moved] = next.splice(sourceIndex, 1);
  next.splice(targetIndex, 0, moved!);
  draggingStopId.value = null;
  await reorderStops(next);
}

async function toggleFullscreen(): Promise<void> {
  if (!mapShell.value) return;
  if (document.fullscreenElement) {
    await document.exitFullscreen();
  } else {
    await mapShell.value.requestFullscreen();
  }
}

function formatDayDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value}T00:00:00`));
}

onMounted(loadPage);
watch([tripId, dayId], loadPage);
</script>

<template>
  <main ref="mapShell" class="map-page map-page--immersive">
    <div v-if="loading" class="map-immersive-state" aria-label="正在加载地图">
      <RefreshCw :size="20" :stroke-width="1.7" class="is-spinning" />
      <span>正在载入路书</span>
    </div>

    <div v-else-if="!trip || !itinerary" class="map-immersive-state map-immersive-state--error">
      <strong>无法打开地图</strong>
      <span>{{ error }}</span>
      <button class="quiet-action" type="button" @click="loadPage">重新加载</button>
    </div>

    <template v-else>
      <MapCanvas
        :stops="displayStops"
        :legs="displayLegs"
        :days="days"
        :center="mapCenter"
        :empty-label="
          trip.brief.origin
            ? `${trip.brief.origin}出发地图`
            : `${trip.brief.destination}地图`
        "
        :zoom="zoom"
        @update:zoom="zoom = $event"
      />

      <aside class="map-route-sheet" aria-label="多日行程路书">
        <div class="map-route-sheet__utility">
          <RouterLink :to="`/trips/${tripId}/itinerary`">
            <ArrowLeft :size="16" :stroke-width="1.8" />
            退出路书
          </RouterLink>
          <button type="button" aria-label="全屏查看地图" @click="toggleFullscreen">
            <Expand :size="17" :stroke-width="1.8" />
          </button>
        </div>

        <header class="map-trip-heading">
          <span>{{ dateRange }}</span>
          <h1>{{ trip.brief.destination }}</h1>
          <p>{{ trip.brief.party_size }} 人 · {{ days.length }} 天</p>
        </header>

        <nav class="map-day-list" aria-label="切换行程日期">
          <RouterLink
            :to="`/trips/${tripId}/map`"
            :class="{ 'is-active': !dayId }"
          >
            <span class="map-day-list__number map-day-list__number--all">全</span>
            <span class="map-day-list__copy">
              <strong>全程路线</strong>
              <small>{{ days.length }} 天 · {{ allStops.length }} 个地点</small>
            </span>
            <span class="map-day-list__dots" aria-hidden="true">
              <i /><i /><i />
            </span>
          </RouterLink>
          <RouterLink
            v-for="(item, index) in days"
            :key="item.id"
            :to="`/trips/${tripId}/days/${item.id}/map`"
            :class="{ 'is-active': item.id === dayId }"
          >
            <span class="map-day-list__number">{{ index + 1 }}</span>
            <span class="map-day-list__copy">
              <strong>{{ item.theme || `第 ${index + 1} 天` }}</strong>
              <small>{{ formatDayDate(item.date) }}</small>
            </span>
            <span class="map-day-list__dots" aria-hidden="true">
              <i /><i /><i />
            </span>
          </RouterLink>
        </nav>

        <section v-if="day" class="map-active-day">
          <header>
            <div>
              <span>第 {{ day.day_index }} 天</span>
              <strong>{{ formatDayDate(day.date) }}</strong>
            </div>
            <div class="map-active-day__actions">
              <span>{{ day.stops.length }} 个地点</span>
              <button type="button" @click="openAddStop">
                <Plus :size="14" :stroke-width="1.9" />
                添加地点
              </button>
            </div>
          </header>

          <form
            v-if="stopEditorOpen"
            class="map-stop-editor"
            @submit.prevent="saveStop"
          >
            <PlacePicker
              :token="auth.token || ''"
              :city="trip.brief.destination"
              @select="selectStopPlace"
            />
            <div class="map-stop-editor__grid">
              <label class="field">
                <span>地点名称</span>
                <span class="field__control">
                  <input v-model="stopForm.placeName" maxlength="200" required />
                </span>
              </label>
              <label class="field">
                <span>开始时间</span>
                <span class="field__control">
                  <input v-model="stopForm.time" type="time" required />
                </span>
              </label>
              <label class="field">
                <span>停留分钟</span>
                <span class="field__control">
                  <input v-model="stopForm.duration" type="number" min="1" max="1440" />
                </span>
              </label>
              <label class="field">
                <span>预计花费</span>
                <span class="field__control">
                  <input v-model="stopForm.cost" inputmode="decimal" placeholder="0" />
                </span>
              </label>
            </div>
            <p v-if="stopForm.source" class="map-stop-editor__source">
              {{ stopForm.source.provider }} · {{ stopForm.source.freshness }} ·
              {{ stopForm.source.queried_at.slice(0, 16).replace("T", " ") }}
            </p>
            <p v-if="stopEditorError" class="form-error" role="alert">
              {{ stopEditorError }}
            </p>
            <footer>
              <button class="quiet-action" type="button" @click="stopEditorOpen = false">
                取消
              </button>
              <button class="primary-button" type="submit" :disabled="stopSaving">
                {{ stopSaving ? "保存中" : editingStopId ? "保存修改" : "添加地点" }}
              </button>
            </footer>
          </form>

          <div class="map-route-controls">
            <button
              type="button"
              :disabled="calculating"
              @click="calculateAllRoutes(true)"
            >
              <Navigation :size="15" :stroke-width="1.8" />
              {{ calculating ? "计算中" : "计算全部路线" }}
            </button>
          </div>

          <p v-if="routeError" class="map-route-notice" role="status">
            {{ routeError }}
          </p>

          <ol v-if="day.stops.length" class="route-stop-list">
            <template v-for="(stop, index) in day.stops" :key="stop.id">
              <li
                class="route-stop"
                :class="{ 'is-dragging': draggingStopId === stop.id }"
                draggable="true"
                data-testid="map-stop"
                @dragstart="draggingStopId = stop.id"
                @dragend="draggingStopId = null"
                @dragover.prevent
                @drop.prevent="dropStop(stop.id)"
              >
                <span class="route-stop__drag" aria-hidden="true">
                  <GripVertical :size="14" :stroke-width="1.7" />
                </span>
                <span class="route-stop__marker">{{ index + 1 }}</span>
                <span class="route-stop__copy">
                  <strong>{{ stop.place_name || stop.place_id }}</strong>
                  <small>
                    {{ stop.start_at.slice(11, 16) }} · {{ stop.duration_minutes }} 分钟
                  </small>
                </span>
                <span class="route-stop__actions">
                  <button
                    type="button"
                    :aria-label="`上移 ${stop.place_name || stop.place_id}`"
                    :disabled="index === 0"
                    @click="moveStop(index, -1)"
                  >
                    <ChevronUp :size="14" :stroke-width="1.8" />
                  </button>
                  <button
                    type="button"
                    :aria-label="`下移 ${stop.place_name || stop.place_id}`"
                    :disabled="index === day.stops.length - 1"
                    @click="moveStop(index, 1)"
                  >
                    <ChevronDown :size="14" :stroke-width="1.8" />
                  </button>
                  <button
                    type="button"
                    :aria-label="`编辑 ${stop.place_name || stop.place_id}`"
                    @click="openEditStop(stop)"
                  >
                    <Edit3 :size="14" :stroke-width="1.8" />
                  </button>
                  <button
                    type="button"
                    :aria-label="`删除 ${stop.place_name || stop.place_id}`"
                    @click="deleteStop(stop)"
                  >
                    <Trash2 :size="14" :stroke-width="1.8" />
                  </button>
                </span>
              </li>
              <li
                v-if="index < day.stops.length - 1"
                class="route-leg"
                :class="{ 'route-leg--error': segments[index]?.status === 'error' }"
              >
                <label>
                  <span>前往下一站</span>
                  <select
                    :value="legModes[index]"
                    :aria-label="`第 ${index + 1} 段交通方式`"
                    @change="handleModeChange(index, $event)"
                  >
                    <optgroup label="城市交通">
                      <option value="walking">步行</option>
                      <option value="driving">驾车</option>
                      <option value="bicycling">骑行</option>
                      <option value="bus">公交</option>
                      <option value="subway">地铁</option>
                    </optgroup>
                    <optgroup label="跨城交通">
                      <option value="flight">飞机（示意航线）</option>
                    </optgroup>
                  </select>
                </label>
                <template v-if="segments[index]?.status === 'missing_coordinates'">
                  <MapPin :size="14" :stroke-width="1.7" />
                  缺少地点坐标
                </template>
                <template v-else-if="segments[index]?.status === 'not_calculated'">
                  <Route :size="14" :stroke-width="1.7" />
                  尚未计算路线
                </template>
                <template v-else-if="segments[index]?.status === 'error'">
                  <TriangleAlert :size="14" :stroke-width="1.7" />
                  {{ segments[index]?.error ? friendlyRouteError(segments[index].error) : "" }}
                </template>
                <template v-else-if="segments[index]?.leg">
                  <span>
                    {{
                      segments[index]!.leg!.provider === "schematic_arc"
                        ? "飞机（示意）"
                        : modeLabels[segments[index]!.leg!.mode]
                    }}
                  </span>
                  <strong>{{ formatDistance(segments[index]!.leg!.distance_m) }}</strong>
                  <span>
                    <template
                      v-if="segments[index]!.leg!.provider === 'schematic_arc'"
                    >
                      示意航程
                    </template>
                    <template v-else>
                      <Clock3 :size="13" :stroke-width="1.7" />
                      {{ formatDuration(segments[index]!.leg!.duration_s) }}
                    </template>
                  </span>
                </template>
              </li>
            </template>
          </ol>

          <p
            v-if="day.stops.length < 2 && allLegs.length === 0"
            class="route-panel__empty"
          >
            至少需要两个地点才能计算路线。
          </p>
        </section>

        <section v-else class="map-active-day map-overview">
          <header>
            <div>
              <span>全程概览</span>
              <strong>{{ days.length }} 天 · {{ allStops.length }} 个地点</strong>
            </div>
            <span>{{ allLegs.length }} 段路线</span>
          </header>
          <div class="map-route-controls">
            <button
              type="button"
              :disabled="calculating"
              @click="calculateAllRoutes(true)"
            >
              <Navigation :size="15" :stroke-width="1.8" />
              {{ calculating ? "计算中" : "计算全部路线" }}
            </button>
          </div>
          <p v-if="routeError" class="map-route-notice" role="status">
            {{ routeError }}
          </p>
          <p v-if="!allStops.length" class="route-panel__empty">
            行程中还没有地点。
          </p>
          <div v-else class="map-overview__days">
            <article v-for="item in days" :key="item.id">
              <span>第 {{ item.day_index }} 天</span>
              <strong>{{ item.theme || formatDayDate(item.date) }}</strong>
              <small>{{ item.stops.length }} 个地点</small>
            </article>
          </div>
        </section>
      </aside>
    </template>

    <Transition name="dialog-fade">
      <div
        v-if="modeWarning"
        class="dialog-backdrop"
        role="presentation"
        @click.self="modeWarning = null"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="mode-warning-title"
        >
          <header>
            <h2 id="mode-warning-title">
              {{ modeLabels[modeWarning.selected] }}距离过长
            </h2>
          </header>
          <p>
            两点直线距离约 {{ formatDistance(modeWarning.distance) }}，
            {{ modeLabels[modeWarning.selected] }}路线可能无法计算。建议改为驾车、公交、地铁或飞机。
          </p>
          <footer>
            <button class="quiet-action" type="button" @click="modeWarning = null">
              取消
            </button>
            <button class="quiet-action" type="button" @click="switchWarningToDriving">
              改为驾车
            </button>
            <button class="primary-button" type="button" @click="acceptModeWarning">
              仍要尝试
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
