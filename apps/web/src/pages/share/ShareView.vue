<!-- 文件说明：前端页面：ShareView。 -->
<script setup lang="ts">
import { CalendarDays, Download, MapPin, Printer, UsersRound } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { shareApi } from "../../features/share/api";
import { exportTripImage, printTripPdf } from "../../features/share/export";
import type { PublicTrip } from "../../features/share/types";

const route = useRoute();
const trip = ref<PublicTrip | null>(null);
const loading = ref(true);
const error = ref("");

const token = () =>
  typeof route.params.token === "string" ? route.params.token : "";

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    trip.value = await shareApi.publicTrip(token());
  } catch {
    error.value = "分享链接不存在、已过期或已被撤销。";
  } finally {
    loading.value = false;
  }
}

async function exportImage(): Promise<void> {
  if (!trip.value) return;
  await exportTripImage(trip.value, `tripmate-${trip.value.destination}-${trip.value.version}`);
}

function exportPdf(): void {
  if (trip.value) printTripPdf(trip.value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value}T00:00:00`));
}

onMounted(load);
</script>

<template>
  <main class="share-page">
    <header class="share-topbar">
      <RouterLink to="/" class="share-brand">TripMate</RouterLink>
      <RouterLink to="/" class="quiet-action">打开我的旅行工作台</RouterLink>
    </header>

    <div v-if="loading" class="share-state">正在打开分享路书</div>
    <div v-else-if="!trip" class="share-state share-state--error">
      <strong>无法打开这份路书</strong>
      <span>{{ error }}</span>
    </div>

    <article v-else class="shared-itinerary">
      <header>
        <div>
          <h1>{{ trip.destination }}</h1>
          <div class="shared-itinerary__facts">
            <span><CalendarDays :size="14" />{{ trip.start_date }} 至 {{ trip.end_date }}</span>
            <span><UsersRound :size="14" />{{ trip.party_size }} 人</span>
            <span>版本 v{{ trip.version }}</span>
          </div>
        </div>
        <div class="shared-itinerary__actions">
          <button class="quiet-action" type="button" @click="exportImage">
            <Download :size="15" :stroke-width="1.8" />
            导出图片
          </button>
          <button class="primary-button" type="button" @click="exportPdf">
            <Printer :size="15" :stroke-width="1.8" />
            打印 / PDF
          </button>
        </div>
      </header>

      <div class="shared-days">
        <section v-for="day in trip.days" :key="day.date" class="shared-day">
          <div class="shared-day__heading">
            <span>第 {{ day.day_index }} 天</span>
            <strong>{{ formatDate(day.date) }}</strong>
            <p>{{ day.theme || "自由安排" }}</p>
          </div>
          <ol v-if="day.stops.length">
            <li v-for="stop in day.stops" :key="`${day.date}-${stop.place_id}`">
              <span class="shared-stop__marker"><MapPin :size="14" /></span>
              <span>
                <strong>{{ stop.place_name || stop.place_id }}</strong>
                <small>{{ stop.start_at.slice(11, 16) }} · {{ stop.duration_minutes }} 分钟</small>
              </span>
            </li>
          </ol>
          <p v-else class="shared-day__empty">这一天还没有地点</p>
        </section>
      </div>

      <footer>
        这是只读旅行路书。行程内容固定在分享时的 v{{ trip.version }}，不包含账号、预算明细或私密备注。
      </footer>
    </article>
  </main>
</template>
