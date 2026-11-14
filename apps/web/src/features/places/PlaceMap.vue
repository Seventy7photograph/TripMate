<!-- 文件说明：前端功能模块：PlaceMap。 -->
<script setup lang="ts">
import { MapPin } from "lucide-vue-next";
import type {
  Map as MapLibreMap,
  Marker as MapLibreMarker,
  StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";

import type { Place } from "./types";

const props = defineProps<{
  places: Place[];
  selectedId: string | null;
}>();

const emit = defineEmits<{
  select: [place: Place];
}>();

const container = ref<HTMLElement | null>(null);
const loading = ref(true);
const error = ref("");
const map = shallowRef<MapLibreMap | null>(null);
const mapLibrary = shallowRef<typeof import("maplibre-gl") | null>(null);
const markers = shallowRef<MapLibreMarker[]>([]);
let resizeObserver: ResizeObserver | null = null;

const locatedPlaces = computed(() =>
  props.places.filter((place) => place.location !== null),
);

const style: StyleSpecification = {
  version: 8,
  sources: {
    amap: {
      type: "raster",
      tiles: [1, 2, 3, 4].map(
        (subdomain) =>
          `https://webrd0${subdomain}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}`,
      ),
      tileSize: 256,
      attribution: "高德地图",
    },
  },
  layers: [
    {
      id: "amap-raster",
      type: "raster",
      source: "amap",
      minzoom: 3,
      maxzoom: 18,
    },
  ],
};

function popupContent(place: Place): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-stop-popup";
  const name = document.createElement("strong");
  name.textContent = place.name;
  const category = document.createElement("span");
  category.textContent = place.category || "地点";
  const address = document.createElement("small");
  address.textContent = place.address || "地址信息缺失";
  root.append(name, category, address);
  return root;
}

function clearMarkers(): void {
  for (const marker of markers.value) marker.remove();
  markers.value = [];
}

function fitPlaces(): void {
  if (!map.value || !mapLibrary.value || !locatedPlaces.value.length) return;
  const bounds = new mapLibrary.value.LngLatBounds();
  for (const place of locatedPlaces.value) {
    if (place.location) {
      bounds.extend([place.location.longitude, place.location.latitude]);
    }
  }
  if (bounds.isEmpty()) return;
  map.value.fitBounds(bounds, {
    padding: 54,
    maxZoom: 15,
    duration: 550,
  });
}

function drawMarkers(): void {
  const maplibregl = mapLibrary.value;
  if (!map.value || !maplibregl) return;
  clearMarkers();
  markers.value = locatedPlaces.value.flatMap((place, index) => {
    if (!place.location) return [];
    const element = document.createElement("button");
    element.type = "button";
    element.className = "place-map-marker";
    element.classList.toggle("is-selected", place.provider_place_id === props.selectedId);
    element.textContent = String(index + 1);
    element.setAttribute("aria-label", `查看地图地点 ${place.name}`);
    element.addEventListener("click", () => emit("select", place));
    return new maplibregl.Marker({ element, anchor: "bottom" })
      .setLngLat([place.location.longitude, place.location.latitude])
      .setPopup(
        new maplibregl.Popup({ offset: 20, closeButton: false }).setDOMContent(
          popupContent(place),
        ),
      )
      .addTo(map.value as MapLibreMap);
  });
}

function refresh(): void {
  drawMarkers();
  fitPlaces();
}

onMounted(async () => {
  await nextTick();
  if (!container.value) return;
  try {
    const maplibregl = await import("maplibre-gl");
    maplibregl.setWorkerUrl(maplibreWorkerUrl);
    mapLibrary.value = maplibregl;
    const nextMap = new maplibregl.Map({
      container: container.value,
      style,
      center: [104.1954, 35.8617],
      zoom: 3.5,
      minZoom: 3,
      maxZoom: 18,
      attributionControl: false,
    });
    map.value = nextMap;
    if (container.value) {
      resizeObserver = new ResizeObserver(() => {
        nextMap.resize();
        if (!loading.value) fitPlaces();
      });
      resizeObserver.observe(container.value);
    }
    nextMap.on("load", () => {
      loading.value = false;
      refresh();
    });
    nextMap.on("error", () => {
      error.value = "地图加载失败";
      loading.value = false;
    });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "地图初始化失败";
    loading.value = false;
  }
});

watch(
  () => [props.places, props.selectedId],
  () => {
    if (!loading.value) refresh();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
  clearMarkers();
  map.value?.remove();
  map.value = null;
  mapLibrary.value = null;
});
</script>

<template>
  <section
    class="places-map"
    data-testid="places-map"
    :data-map-ready="!loading && !error ? 'true' : 'false'"
    aria-label="地点搜索结果地图"
  >
    <div ref="container" class="places-map__canvas" />
    <div class="places-map__label">
      <MapPin :size="15" :stroke-width="1.8" />
      <span>{{ locatedPlaces.length }} 个地图地点</span>
    </div>
    <div v-if="loading" class="places-map__state">正在加载地图</div>
    <div v-else-if="error" class="places-map__state" role="alert">{{ error }}</div>
  </section>
</template>
