<!-- 文件说明：前端功能模块：ItineraryDayEditor。 -->
<script setup lang="ts">
import { Clock3, Map, Plus } from "lucide-vue-next";
import { reactive, ref, watch } from "vue";

import LeafActionButton from "../../components/LeafActionButton.vue";
import { parseAmountToMinor } from "./form";
import PlacePicker from "../places/PlacePicker.vue";
import type { Place } from "../places/types";
import type { CreateStopInput, ItineraryStop, TripDay } from "./types";
import ItineraryStopEditor from "./ItineraryStopEditor.vue";

type NewStopInput = Omit<CreateStopInput, "expected_version">;

const props = defineProps<{
  day: TripDay;
  city?: string;
  authToken?: string;
  currency: string;
  adding: boolean;
  addError: string;
  dayMessage: string;
  resetKey: number;
  savingStopId: string | null;
  movingStopId: string | null;
  draftResetKeys: Record<string, number>;
  saveStopHandler: (
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
  ) => Promise<void>;
}>();

const emit = defineEmits<{
  "add-stop": [dayId: string, input: NewStopInput];
  "delete-stop": [dayId: string, stop: ItineraryStop];
  "move-stop": [dayId: string, stopId: string, direction: -1 | 1];
}>();

const form = reactive({
  placeName: "",
  time: "09:00",
  duration: "60",
  cost: "",
  longitude: "",
  latitude: "",
  coordinateSystem: "GCJ-02" as "GCJ-02" | "WGS84",
  placeId: "",
  source: null as ItineraryStop["source"] | null,
});
const formError = ref("");

function suggestedTime(): string {
  const lastStop = props.day.stops.at(-1);
  if (!lastStop) return "09:00";

  const [hours = "0", minutes = "0"] = lastStop.start_at.slice(11, 16).split(":");
  const totalMinutes =
    Number(hours) * 60 + Number(minutes) + lastStop.duration_minutes;
  return `${String(Math.floor(totalMinutes / 60) % 24).padStart(2, "0")}:${String(
    totalMinutes % 60,
  ).padStart(2, "0")}`;
}

watch(
  () => props.resetKey,
  () => {
    form.placeName = "";
    form.cost = "";
    form.longitude = "";
    form.latitude = "";
    form.coordinateSystem = "GCJ-02";
    form.placeId = "";
    form.source = null;
    form.time = suggestedTime();
    formError.value = "";
  },
);

function addStop(): void {
  formError.value = "";
  const placeName = form.placeName.trim();
  const duration = Number(form.duration);
  const cost = parseAmountToMinor(form.cost);
  const hasLongitude = Boolean(form.longitude.trim());
  const hasLatitude = Boolean(form.latitude.trim());
  const longitude = Number(form.longitude);
  const latitude = Number(form.latitude);
  if (!placeName) {
    formError.value = "请填写地点名称。";
    return;
  }
  if (!/^\d{2}:\d{2}$/.test(form.time)) {
    formError.value = "请选择开始时间。";
    return;
  }
  if (!Number.isInteger(duration) || duration < 1 || duration > 1440) {
    formError.value = "停留时间需为 1 到 1440 分钟。";
    return;
  }
  if (cost === undefined) {
    formError.value = "预计花费最多保留两位小数。";
    return;
  }
  if (
    hasLongitude !== hasLatitude ||
    (hasLongitude &&
      (!Number.isFinite(longitude) ||
        longitude < -180 ||
        longitude > 180 ||
        !Number.isFinite(latitude) ||
        latitude < -90 ||
        latitude > 90))
  ) {
    formError.value = "经纬度需同时填写，经度 -180 到 180，纬度 -90 到 90。";
    return;
  }

  emit("add-stop", props.day.id, {
    place_id: form.placeId || `manual-${crypto.randomUUID()}`,
    place_name: placeName,
    start_at: `${props.day.date}T${form.time}:00`,
    duration_minutes: duration,
    estimated_cost_minor: cost ?? 0,
    location:
      hasLongitude && hasLatitude
        ? {
            longitude,
            latitude,
            coordinate_system: form.coordinateSystem,
          }
        : null,
    source: form.source,
  });
}

function selectPlace(place: Place): void {
  form.placeName = place.name;
  form.placeId = place.provider_place_id;
  form.longitude = place.location ? String(place.location.longitude) : "";
  form.latitude = place.location ? String(place.location.latitude) : "";
  form.coordinateSystem = place.location?.coordinate_system ?? "GCJ-02";
  form.source = place.source;
  formError.value = "";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value}T00:00:00`));
}
</script>

<template>
<section class="itinerary-day" data-testid="itinerary-day">
  <header class="itinerary-day__heading">
    <div>
      <span>第 {{ day.day_index }} 天</span>
      <h2>{{ formatDate(day.date) }}</h2>
      <p>{{ day.theme || "还没有设置当天主题" }}</p>
    </div>
    <div class="itinerary-day__actions">
      <span class="itinerary-day__count">{{ day.stops.length }} 个地点</span>
      <LeafActionButton
        label="地图与路线"
        :to="`/trips/${day.trip_id}/days/${day.id}/map`"
      >
        <template #icon>
          <Map :size="15" :stroke-width="1.8" />
        </template>
      </LeafActionButton>
    </div>
  </header>

  <p v-if="dayMessage" class="itinerary-day__message" role="status">
    {{ dayMessage }}
  </p>

  <div v-if="day.stops.length" class="itinerary-stop-list">
    <ItineraryStopEditor
      v-for="(stop, index) in day.stops"
      :key="stop.id"
      :stop="stop"
      :day-date="day.date"
      :currency="currency"
      :index="index"
      :is-first="index === 0"
      :is-last="index === day.stops.length - 1"
      :saving="savingStopId === stop.id"
      :moving="movingStopId === stop.id"
      :draft-reset-key="draftResetKeys[stop.id] ?? 0"
      :save-handler="(input) => saveStopHandler(day.id, stop.id, input)"
      @delete="(stop) => emit('delete-stop', day.id, stop)"
      @move="(stopId, direction) => emit('move-stop', day.id, stopId, direction)"
    />
  </div>

  <div v-else class="itinerary-day__empty">
    <Clock3 :size="18" :stroke-width="1.7" />
    <span>这一天还没有地点，从下面的表单添加。</span>
  </div>

  <form class="itinerary-add-stop" data-testid="itinerary-add-stop" @submit.prevent="addStop">
    <div class="itinerary-add-stop__heading">
      <strong>添加地点</strong>
      <span>搜索真实地点，坐标与来源自动带入</span>
    </div>

    <PlacePicker
      v-if="authToken"
      :token="authToken"
      :city="city"
      @select="selectPlace"
    />

    <div class="itinerary-add-stop__grid">
      <label class="field">
        <span>地点名称</span>
        <span class="field__control">
          <input
            v-model="form.placeName"
            maxlength="200"
            placeholder="搜索后自动填入，或手工填写"
            required
          />
        </span>
      </label>

      <label class="field">
        <span>开始时间</span>
        <span class="field__control">
          <input v-model="form.time" type="time" required />
        </span>
      </label>

      <label class="field">
        <span>停留分钟</span>
        <span class="field__control">
          <input v-model="form.duration" type="number" min="1" max="1440" required />
        </span>
      </label>

      <label class="field">
        <span>预计花费</span>
        <span class="field__control">
          <input v-model="form.cost" inputmode="decimal" placeholder="0" />
        </span>
      </label>

      <button class="primary-button itinerary-add-stop__button" type="submit" :disabled="adding">
        <Plus :size="16" :stroke-width="1.9" />
        {{ adding ? "添加中" : "添加地点" }}
      </button>
    </div>

    <details class="itinerary-add-stop__coords">
      <summary>坐标与来源（可选）</summary>
      <label class="field">
        <span>经度</span>
        <span class="field__control">
          <input v-model="form.longitude" inputmode="decimal" placeholder="可选，例如 106.579109" />
        </span>
      </label>

      <label class="field">
        <span>纬度</span>
        <span class="field__control">
          <input v-model="form.latitude" inputmode="decimal" placeholder="可选，例如 29.562819" />
        </span>
      </label>

      <label class="field">
        <span>坐标系</span>
        <span class="field__control">
          <select v-model="form.coordinateSystem">
            <option value="GCJ-02">GCJ-02</option>
            <option value="WGS84">WGS84</option>
          </select>
        </span>
      </label>
    </details>

    <p v-if="formError || addError" class="form-error" role="alert">
      {{ formError || addError }}
    </p>
  </form>
</section>
</template>
