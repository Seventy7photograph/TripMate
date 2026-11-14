<!-- 文件说明：前端功能模块：TravelPlanCard。 -->
<script lang="ts" setup>
import {
  ArrowUpRight,
  BedDouble,
  CalendarDays,
  CloudSun,
  Map,
  Route,
  ShieldCheck,
  Sparkles,
  Utensils,
} from "lucide-vue-next";
import { computed } from "vue";
import { RouterLink } from "vue-router";

import { formatMoney } from "../budget/form";
import type { ItineraryDraft } from "../planning/types";
import type { Trip } from "../trips/types";

const props = defineProps<{
  trip: Trip;
  itinerary: ItineraryDraft;
  mapDayId?: string;
  status?: "completed" | "partial";
}>();

const totalEstimatedMinor = computed(() =>
  props.itinerary.days.reduce(
    (total, day) =>
      total +
      day.stops.reduce((dayTotal, stop) => dayTotal + stop.estimated_cost_minor, 0),
    0,
  ),
);

const stopCount = computed(() =>
  props.itinerary.days.reduce((total, day) => total + day.stops.length, 0),
);

const firstDayId = computed(() => props.mapDayId || "");

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value}T00:00:00`));
}

function stopNames(day: ItineraryDraft["days"][number]): string {
  return day.stops
    .map((stop) => stop.place_name || stop.place_id)
    .join(" · ");
}

function mealLabel(meal: "breakfast" | "lunch" | "dinner"): string {
  return {
    breakfast: "早餐",
    lunch: "午餐",
    dinner: "晚餐",
  }[meal];
}
</script>

<template>
  <article class="travel-plan-card">
    <header class="travel-plan-card__heading">
      <div>
        <span class="travel-plan-card__status">
          {{ status === "partial" ? "部分结果" : "已生成" }}
        </span>
        <h2>{{ trip.brief.destination }}</h2>
        <p>
          {{ trip.brief.start_date }} 至 {{ trip.brief.end_date }} ·
          {{ trip.brief.party_size }} 人
        </p>
      </div>
      <strong>{{ formatMoney(totalEstimatedMinor, trip.brief.currency) }}</strong>
    </header>

    <div class="travel-plan-card__facts">
      <span><CalendarDays :size="14" />{{ itinerary.days.length }} 天</span>
      <span><Route :size="14" />{{ stopCount }} 个地点</span>
      <span>预计 {{ formatMoney(totalEstimatedMinor, trip.brief.currency) }}</span>
    </div>

    <div class="travel-plan-card__table-wrap">
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>主题</th>
            <th>地点</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="day in itinerary.days" :key="day.id">
            <td>{{ formatDate(day.date) }}</td>
            <td>{{ day.theme || `第 ${itinerary.days.indexOf(day) + 1} 天` }}</td>
            <td>{{ stopNames(day) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <section class="travel-plan-card__day-details" aria-label="每日旅行信息">
      <article
        v-for="(day, index) in itinerary.days"
        :key="`${day.id}-details`"
        class="travel-plan-day-detail"
      >
        <header>
          <span>第 {{ index + 1 }} 天</span>
          <strong>{{ formatDate(day.date) }}</strong>
        </header>
        <p v-if="day.daily_summary" class="travel-plan-day-detail__summary">
          {{ day.daily_summary }}
        </p>
        <div class="travel-plan-day-detail__grid">
          <div>
            <CloudSun :size="15" />
            <span>天气</span>
            <strong>
              {{
                day.weather?.status === "known"
                  ? day.weather.summary || "已确认"
                  : "未确认"
              }}
            </strong>
            <small v-if="day.weather?.clothing_advice.length">
              {{ day.weather.clothing_advice.join("；") }}
            </small>
          </div>
          <div>
            <Utensils :size="15" />
            <span>餐饮</span>
            <strong>
              {{
                day.meals?.length
                  ? day.meals
                      .map(
                        (meal) =>
                          `${mealLabel(meal.meal)}：${meal.place_name || "未确认"}`,
                      )
                      .join(" · ")
                  : "未确认"
              }}
            </strong>
          </div>
          <div>
            <BedDouble :size="15" />
            <span>住宿区域</span>
            <strong>
              {{
                day.lodging_area?.status === "known"
                  ? day.lodging_area.area || "已确认"
                  : "未确认"
              }}
            </strong>
            <small v-if="day.lodging_area?.reason">
              {{ day.lodging_area.reason }}
            </small>
          </div>
          <div>
            <ShieldCheck :size="15" />
            <span>安全</span>
            <strong>
              {{
                day.safety?.reminders.length
                  ? day.safety.reminders.join("；")
                  : "暂无额外提醒"
              }}
            </strong>
          </div>
          <div v-if="day.transport?.length">
            <Route :size="15" />
            <span>交通</span>
            <strong>
              {{
                day.transport
                  .map((item) => item.summary || item.mode)
                  .join(" · ")
              }}
            </strong>
          </div>
          <div v-if="day.alternatives?.length">
            <Sparkles :size="15" />
            <span>备选</span>
            <strong>{{ day.alternatives.join("；") }}</strong>
          </div>
        </div>
      </article>
    </section>

    <ul
      v-if="itinerary.validation_summary.length"
      class="travel-plan-card__issues"
    >
      <li
        v-for="issue in itinerary.validation_summary"
        :key="`${issue.path}-${issue.code}`"
      >
        {{ issue.message }}
      </li>
    </ul>

    <footer class="travel-plan-card__links">
      <RouterLink :to="`/trips/${trip.id}`">
        旅行详情
        <ArrowUpRight :size="14" />
      </RouterLink>
      <RouterLink :to="`/trips/${trip.id}/itinerary`">
        逐日行程
        <ArrowUpRight :size="14" />
      </RouterLink>
      <RouterLink
        v-if="firstDayId"
        :to="`/trips/${trip.id}/map`"
      >
        <Map :size="14" />
        全屏地图
      </RouterLink>
    </footer>
  </article>
</template>
