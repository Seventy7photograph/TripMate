<!-- 文件说明：前端功能模块：ItineraryStopEditor。 -->
<script setup lang="ts">
import {
  ChevronDown,
  ChevronUp,
  Save,
  Trash2,
} from "lucide-vue-next";
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";

import { useAutosave } from "../../composables/useAutosave";
import { dateTimeFor, parseAmountToMinor, timeFromDateTime } from "./form";
import type { ItineraryStop } from "./types";

const props = defineProps<{
  stop: ItineraryStop;
  dayDate: string;
  currency: string;
  index: number;
  isFirst: boolean;
  isLast: boolean;
  saving: boolean;
  moving: boolean;
  draftResetKey: number;
  saveHandler: (input: {
    start_at: string;
    duration_minutes: number;
    estimated_cost_minor: number;
    location: {
      longitude: number;
      latitude: number;
      coordinate_system: "GCJ-02" | "WGS84";
    } | null;
  }) => Promise<void>;
}>();

const emit = defineEmits<{
  delete: [stop: ItineraryStop];
  move: [stopId: string, direction: -1 | 1];
}>();

interface StopDraft {
  time: string;
  duration: string;
  cost: string;
  longitude: string;
  latitude: string;
  coordinateSystem: "GCJ-02" | "WGS84";
}

const form = reactive({
  time: timeFromDateTime(props.stop.start_at),
  duration: String(props.stop.duration_minutes),
  cost: (props.stop.estimated_cost_minor / 100).toFixed(2).replace(/\.00$/, ""),
  longitude: props.stop.location ? String(props.stop.location.longitude) : "",
  latitude: props.stop.location ? String(props.stop.location.latitude) : "",
  coordinateSystem: props.stop.location?.coordinate_system ?? "GCJ-02",
});
const error = ref("");
const syncingFromServer = ref(false);
const hydrated = ref(false);

function draftFromForm(): StopDraft {
  return {
    time: form.time,
    duration: form.duration,
    cost: form.cost,
    longitude: form.longitude,
    latitude: form.latitude,
    coordinateSystem: form.coordinateSystem,
  };
}

function validDraft(draft: StopDraft): boolean {
  const duration = Number(draft.duration);
  const hasLongitude = Boolean(draft.longitude.trim());
  const hasLatitude = Boolean(draft.latitude.trim());
  const longitude = Number(draft.longitude);
  const latitude = Number(draft.latitude);
  return (
    /^\d{2}:\d{2}$/.test(draft.time) &&
    Number.isInteger(duration) &&
    duration >= 1 &&
    duration <= 1440 &&
    parseAmountToMinor(draft.cost) !== undefined &&
    hasLongitude === hasLatitude &&
    (!hasLongitude ||
      (Number.isFinite(longitude) &&
        longitude >= -180 &&
        longitude <= 180 &&
        Number.isFinite(latitude) &&
        latitude >= -90 &&
        latitude <= 90))
  );
}

function savePayload(draft: StopDraft) {
  return {
    start_at: dateTimeFor(props.dayDate, draft.time),
    duration_minutes: Number(draft.duration),
    estimated_cost_minor: parseAmountToMinor(draft.cost) ?? 0,
    location:
      draft.longitude.trim() && draft.latitude.trim()
        ? {
            longitude: Number(draft.longitude),
            latitude: Number(draft.latitude),
            coordinate_system: draft.coordinateSystem,
          }
        : null,
  };
}

const autosave = useAutosave<StopDraft>({
  key: () => `tripmate.itinerary.stop-draft.${props.stop.id}`,
  save: async (draft) => {
    await props.saveHandler(savePayload(draft));
  },
  delay: 900,
});

const autosaveLabel = computed(() => {
  switch (autosave.status.value) {
    case "pending":
      return "等待自动保存";
    case "saving":
      return "自动保存中";
    case "saved":
      return "已自动保存";
    case "error":
      return "保存失败，草稿已保留";
    default:
      return autosave.hasDraft.value ? "已恢复本地草稿" : "";
  }
});

const stopName = () => props.stop.place_name || props.stop.place_id;

watch(
  () => props.stop,
  async (stop) => {
    syncingFromServer.value = true;
    form.time = timeFromDateTime(stop.start_at);
    form.duration = String(stop.duration_minutes);
    form.cost = (stop.estimated_cost_minor / 100).toFixed(2).replace(/\.00$/, "");
    form.longitude = stop.location ? String(stop.location.longitude) : "";
    form.latitude = stop.location ? String(stop.location.latitude) : "";
    form.coordinateSystem = stop.location?.coordinate_system ?? "GCJ-02";
    error.value = "";
    await nextTick();
    syncingFromServer.value = false;
  },
);

watch(
  form,
  () => {
    if (!hydrated.value || syncingFromServer.value) return;
    const draft = draftFromForm();
    if (!validDraft(draft)) return;
    autosave.schedule(draft);
  },
  { deep: true },
);

watch(
  () => props.draftResetKey,
  () => {
    autosave.discardDraft();
  },
);

onMounted(async () => {
  const draft = autosave.restoreDraft();
  if (draft) {
    form.time = draft.time;
    form.duration = draft.duration;
    form.cost = draft.cost;
    form.longitude = draft.longitude;
    form.latitude = draft.latitude;
    form.coordinateSystem = draft.coordinateSystem;
  }
  await nextTick();
  hydrated.value = true;
  if (draft && validDraft(draft)) {
    autosave.schedule(draft);
  }
});

async function submit(): Promise<void> {
  error.value = "";
  const draft = draftFromForm();
  if (!/^\d{2}:\d{2}$/.test(draft.time)) {
    error.value = "请选择开始时间。";
    return;
  }
  const duration = Number(draft.duration);
  if (!Number.isInteger(duration) || duration < 1 || duration > 1440) {
    error.value = "停留时间需为 1 到 1440 分钟。";
    return;
  }
  if (parseAmountToMinor(draft.cost) === undefined) {
    error.value = "预计花费最多保留两位小数。";
    return;
  }
  if (!validDraft(draft)) {
    error.value = "经纬度需同时填写，经度 -180 到 180，纬度 -90 到 90。";
    return;
  }

  autosave.schedule(draft);
  const saved = await autosave.flush();
  if (!saved) {
    error.value = "保存失败，本地草稿已保留。";
  }
}
</script>

<template>
  <article class="itinerary-stop" data-testid="itinerary-stop">
    <div class="itinerary-stop__order">
      <button
        class="icon-action"
        type="button"
        :aria-label="`上移 ${stopName()}`"
        :disabled="isFirst || moving"
        @click="emit('move', stop.id, -1)"
      >
        <ChevronUp :size="15" :stroke-width="1.8" />
      </button>
      <span>{{ index + 1 }}</span>
      <button
        class="icon-action"
        type="button"
        :aria-label="`下移 ${stopName()}`"
        :disabled="isLast || moving"
        @click="emit('move', stop.id, 1)"
      >
        <ChevronDown :size="15" :stroke-width="1.8" />
      </button>
    </div>

    <div class="itinerary-stop__identity">
      <strong>{{ stopName() }}</strong>
      <span>手动添加 · 来源 {{ stop.source.provider }}</span>
      <span
        v-if="autosaveLabel"
        class="autosave-state"
        :class="`autosave-state--${autosave.status.value}`"
        role="status"
      >
        {{ autosaveLabel }}
      </span>
    </div>

    <div class="itinerary-stop__fields">
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
        <span>预计花费 ({{ currency }})</span>
        <span class="field__control">
          <input v-model="form.cost" inputmode="decimal" placeholder="0" />
        </span>
      </label>
    </div>

    <div class="itinerary-stop__fields itinerary-stop__fields--location">
      <label class="field">
        <span>经度</span>
        <span class="field__control">
          <input v-model="form.longitude" inputmode="decimal" placeholder="可选" />
        </span>
      </label>

      <label class="field">
        <span>纬度</span>
        <span class="field__control">
          <input v-model="form.latitude" inputmode="decimal" placeholder="可选" />
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
    </div>

    <div class="itinerary-stop__actions">
      <button
        class="quiet-action"
        type="button"
        :aria-label="`保存 ${stopName()}`"
        :disabled="saving"
        @click="submit"
      >
        <Save :size="15" :stroke-width="1.8" />
        {{ saving ? "保存中" : "保存" }}
      </button>
      <button
        class="icon-action icon-action--danger"
        type="button"
        :aria-label="`删除 ${stopName()}`"
        @click="emit('delete', stop)"
      >
        <Trash2 :size="16" :stroke-width="1.8" />
      </button>
    </div>

    <p v-if="error" class="itinerary-stop__error" role="alert">{{ error }}</p>
  </article>
</template>
