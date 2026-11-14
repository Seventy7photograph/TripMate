<!-- 文件说明：Vue 组件：MapCanvas。 -->
<script setup lang="ts">
import type { Feature, FeatureCollection, LineString } from "geojson";
import { Minus, Plus, RefreshCw } from "lucide-vue-next";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  Marker as MapLibreMarker,
  StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";

import type {
  ItineraryStop,
  StopLocation,
  TripDay,
} from "../features/itinerary/types";
import type { RouteLeg } from "../features/map/types";

const props = defineProps<{
  stops: ItineraryStop[];
  legs: RouteLeg[];
  zoom: number;
  days?: TripDay[];
  center?: StopLocation | null;
  emptyLabel?: string;
}>();

const emit = defineEmits<{
  "update:zoom": [zoom: number];
}>();

const container = ref<HTMLElement | null>(null);
const loading = ref(true);
const error = ref("");
const map = shallowRef<MapLibreMap | null>(null);
const markers = shallowRef<MapLibreMarker[]>([]);
const mapLibrary = shallowRef<typeof import("maplibre-gl") | null>(null);

const locatedStops = computed(() =>
  props.stops.filter((stop) => stop.location !== null),
);
const dayById = computed(
  () => new Map((props.days ?? []).map((day, index) => [day.id, { day, index }])),
);
const dayColors = [
  "#2167cf",
  "#2d766a",
  "#a36b2b",
  "#87518d",
  "#b24f4f",
  "#4d6b9b",
  "#6b7e5f",
  "#8c643f",
];

function dayColor(dayId: string): string {
  const index = dayById.value.get(dayId)?.index ?? 0;
  return dayColors[index % dayColors.length]!;
}

const providerLabel = computed(() =>
  props.legs.length && props.legs.every((leg) => leg.provider === "schematic_arc")
    ? "飞机示意航线"
    : props.legs[0]?.provider === "amap"
      ? "© 高德地图"
      : props.legs.length
        ? `路线 Provider · ${props.legs[0]?.provider}`
        : "© 高德地图",
);

const amapStyle: StyleSpecification = {
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

function routeFeatures(): FeatureCollection<LineString> {
  const features: Array<Feature<LineString>> = [];
  for (const leg of props.legs) {
    if (!leg.polyline) continue;
    const coordinates = leg.polyline
      .split(";")
      .map((point) => point.split(",").map(Number))
      .filter(
        (point) =>
          point.length === 2 &&
          Number.isFinite(point[0]) &&
          Number.isFinite(point[1]),
      )
      .map(([longitude, latitude]) => [longitude, latitude] as [number, number]);
    if (coordinates.length < 2) continue;
    features.push({
      type: "Feature",
      properties: {
        provider: leg.provider,
        distance_m: leg.distance_m,
        duration_s: leg.duration_s,
        mode: leg.mode,
        day_id: leg.day_id,
        color: dayColor(leg.day_id),
      },
      geometry: {
        type: "LineString",
        coordinates,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

const routeFeatureCollection = computed(routeFeatures);

function popupContent(stop: ItineraryStop): HTMLElement {
  const root = document.createElement("div");
  const day = dayById.value.get(stop.day_id)?.day;
  const dayLabel = document.createElement("small");
  dayLabel.textContent = day
    ? `Day ${day.day_index} · ${day.date}`
    : stop.start_at.slice(0, 10);
  root.className = "map-stop-popup";
  const name = document.createElement("strong");
  name.textContent = stop.place_name || stop.place_id;
  const time = document.createElement("span");
  time.textContent = `${stop.start_at.slice(11, 16)} · ${stop.duration_minutes} 分钟`;
  const source = document.createElement("small");
  source.textContent = `${stop.source.provider} · ${stop.source.freshness}`;
  root.append(dayLabel, name, time, source);
  return root;
}

function clearMarkers(): void {
  for (const marker of markers.value) marker.remove();
  markers.value = [];
}

function fitMapToStops(): void {
  if (!map.value) return;
  if (!locatedStops.value.length) {
    if (props.center) {
      map.value.jumpTo({
        center: [props.center.longitude, props.center.latitude],
        zoom: 11,
      });
    }
    return;
  }
  const maplibregl = mapLibrary.value;
  if (!maplibregl) return;
  const bounds = new maplibregl.LngLatBounds();
  for (const stop of locatedStops.value) {
    if (!stop.location) continue;
    bounds.extend([stop.location.longitude, stop.location.latitude]);
  }
  if (bounds.isEmpty()) return;
  map.value.fitBounds(bounds, {
    padding: {
      top: 120,
      right: 90,
      bottom: 100,
      left: window.innerWidth > 760 ? 440 : 70,
    },
    maxZoom: 16,
    duration: 700,
  });
}

function drawMarkers(): void {
  const maplibregl = mapLibrary.value;
  if (!map.value || !maplibregl) return;
  clearMarkers();
  const nextMarkers = locatedStops.value.map((stop) => {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "map-stop-marker";
    const dayPosition = dayById.value.get(stop.day_id)?.index ?? 0;
    element.style.setProperty("--marker-color", dayColor(stop.day_id));
    element.textContent = String(stop.order_index + 1);
    element.setAttribute(
      "aria-label",
      `第 ${dayPosition + 1} 天，${stop.place_name || stop.place_id}，${stop.start_at.slice(11, 16)}`,
    );
    if (!stop.location) return null;
    return new maplibregl.Marker({ element, anchor: "bottom" })
      .setLngLat([stop.location.longitude, stop.location.latitude])
      .setPopup(
        new maplibregl.Popup({ offset: 22, closeButton: false }).setDOMContent(
          popupContent(stop),
        ),
      )
      .addTo(map.value as MapLibreMap);
  });
  markers.value = nextMarkers.filter(
    (marker): marker is MapLibreMarker => marker !== null,
  );
}

function drawRoute(): void {
  if (!map.value) return;
  const source = map.value.getSource("day-route") as
    | GeoJSONSource
    | undefined;
  const data = routeFeatureCollection.value;
  if (source) {
    source.setData(data);
  } else {
    map.value.addSource("day-route", {
      type: "geojson",
      data,
    });
    map.value.addLayer({
      id: "day-route-line",
      type: "line",
      source: "day-route",
      paint: {
        "line-color": ["get", "color"],
        "line-width": 5,
        "line-opacity": 0.92,
      },
      layout: {
        "line-cap": "round",
        "line-join": "round",
      },
    });
  }
}

function refreshOverlay(): void {
  if (!map.value) return;
  drawMarkers();
  drawRoute();
  fitMapToStops();
}

function changeZoom(delta: number): void {
  if (!map.value) return;
  const nextZoom = Math.min(18, Math.max(3, map.value.getZoom() + delta));
  map.value.easeTo({ zoom: nextZoom, duration: 220 });
  emit("update:zoom", nextZoom);
}

function refreshMap(): void {
  if (!map.value) return;
  map.value.triggerRepaint();
  refreshOverlay();
}

onMounted(async () => {
  await nextTick();
  if (!container.value) return;
  try {
    const maplibregl = await import("maplibre-gl");
    maplibregl.setWorkerUrl(maplibreWorkerUrl);
    mapLibrary.value = maplibregl;
    const firstLocation = locatedStops.value[0]?.location;
    const center: [number, number] = props.center
      ? [props.center.longitude, props.center.latitude]
      : firstLocation
        ? [firstLocation.longitude, firstLocation.latitude]
        : [104.1954, 35.8617];
    const nextMap = new maplibregl.Map({
      container: container.value,
      style: amapStyle,
      center,
      zoom: props.center && !firstLocation ? 11 : firstLocation ? props.zoom : 4,
      minZoom: 3,
      maxZoom: 18,
      attributionControl: false,
    });
    nextMap.addControl(
      new maplibregl.ScaleControl({
        unit: "metric",
        maxWidth: 120,
      }),
      "bottom-right",
    );
    map.value = nextMap;
    nextMap.on("load", () => {
      loading.value = false;
      refreshOverlay();
    });
    nextMap.on("zoomend", () => {
      emit("update:zoom", nextMap.getZoom());
    });
    nextMap.on("error", () => {
      error.value = "地图瓦片加载失败";
      loading.value = false;
    });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "地图初始化失败";
    loading.value = false;
  }
});

watch(
  () => [props.stops, props.legs, props.days, props.center],
  () => {
    if (!loading.value) refreshOverlay();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  clearMarkers();
  map.value?.remove();
  map.value = null;
  mapLibrary.value = null;
});
</script>

<template>
  <section
    class="map-canvas map-canvas--maplibre"
    data-testid="route-map"
    aria-label="逐日路线地图"
    :data-map-ready="!loading && !error ? 'true' : 'false'"
    :data-route-features="routeFeatureCollection.features.length"
    :data-map-center="
      center
        ? `${center.longitude},${center.latitude}`
        : locatedStops[0]?.location
          ? `${locatedStops[0].location.longitude},${locatedStops[0].location.latitude}`
          : 'china'
    "
  >
    <div ref="container" class="map-canvas__maplibre" />

    <div class="map-canvas__toolbar">
      <span class="map-canvas__status">
        <span class="provider-dot" :class="{ 'provider-dot--live': !loading && !error }" />
        {{
          error
            ? "地图不可用"
            : props.legs.length
              ? "全部行程路线已绘制"
              : props.emptyLabel || "实时地点地图"
        }}
      </span>
      <div>
        <button
          class="icon-action"
          type="button"
          aria-label="放大地图"
          :disabled="zoom >= 18"
          @click="changeZoom(1)"
        >
          <Plus :size="15" :stroke-width="1.8" />
        </button>
        <button
          class="icon-action"
          type="button"
          aria-label="缩小地图"
          :disabled="zoom <= 3"
          @click="changeZoom(-1)"
        >
          <Minus :size="15" :stroke-width="1.8" />
        </button>
        <button class="icon-action" type="button" aria-label="刷新地图" @click="refreshMap">
          <RefreshCw :size="15" :stroke-width="1.8" />
        </button>
      </div>
    </div>

    <div v-if="loading" class="map-canvas__loading" aria-live="polite">
      正在加载高德地图
    </div>
    <div v-if="error" class="map-canvas__error" role="alert">{{ error }}</div>
    <span class="map-canvas__attribution">{{ providerLabel }}</span>
  </section>
</template>
