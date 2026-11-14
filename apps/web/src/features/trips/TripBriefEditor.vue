<!-- 文件说明：前端功能模块：TripBriefEditor。 -->
<script setup lang="ts">
import { CalendarDays, Save, UsersRound } from "lucide-vue-next";
import { reactive, ref, watch } from "vue";

import {
  tripBriefToForm,
  toTripBriefInput,
  validateTripBriefForm,
  type TripBriefFormInput,
} from "./form";
import type { TripBrief } from "./types";

const props = withDefaults(
  defineProps<{
    initialValue?: Partial<TripBrief> | null;
    submitLabel: string;
    submitting?: boolean;
  }>(),
  {
    initialValue: null,
    submitting: false,
  },
);

const emit = defineEmits<{
  submit: [brief: TripBrief];
}>();

const form = reactive<TripBriefFormInput>(tripBriefToForm(props.initialValue));
const error = ref<string | null>(null);

watch(
  () => props.initialValue,
  (value) => {
    Object.assign(form, tripBriefToForm(value));
    error.value = null;
  },
);

function submit(): void {
  error.value = validateTripBriefForm(form);
  if (error.value) return;
  emit("submit", toTripBriefInput(form));
}
</script>

<template>
  <form class="trip-brief-form" @submit.prevent="submit">
    <section class="trip-form-section" aria-labelledby="trip-form-basics">
      <header class="trip-form-section__heading">
        <h2 id="trip-form-basics">路线与日期</h2>
        <span>先确定这次旅行的基本约束</span>
      </header>

      <div class="trip-form-grid trip-form-grid--route">
        <label class="field">
          <span>目的地</span>
          <span class="field__control">
            <input
              v-model.trim="form.destination"
              name="destination"
              maxlength="120"
              required
              placeholder="例如：重庆"
            />
          </span>
        </label>

        <label class="field">
          <span>出发地</span>
          <span class="field__control">
            <input
              v-model.trim="form.origin"
              name="origin"
              maxlength="120"
              placeholder="例如：上海"
            />
          </span>
        </label>
      </div>

      <div class="trip-form-grid trip-form-grid--dates">
        <label class="field">
          <span>开始日期</span>
          <span class="field__control">
            <CalendarDays :size="16" :stroke-width="1.7" aria-hidden="true" />
            <input v-model="form.startDate" name="start_date" type="date" required />
          </span>
        </label>

        <label class="field">
          <span>结束日期</span>
          <span class="field__control">
            <CalendarDays :size="16" :stroke-width="1.7" aria-hidden="true" />
            <input v-model="form.endDate" name="end_date" type="date" required />
          </span>
        </label>

        <label class="field">
          <span>出行人数</span>
          <span class="field__control">
            <UsersRound :size="16" :stroke-width="1.7" aria-hidden="true" />
            <input
              v-model="form.partySize"
              name="party_size"
              type="number"
              min="1"
              max="20"
              required
            />
          </span>
        </label>
      </div>
    </section>

    <section class="trip-form-section" aria-labelledby="trip-form-preference">
      <header class="trip-form-section__heading">
        <h2 id="trip-form-preference">预算与偏好</h2>
        <span>这些内容会进入后续的行程规划</span>
      </header>

      <div class="trip-form-grid trip-form-grid--preferences">
        <label class="field">
          <span>预算 ({{ form.currency.toUpperCase() || "CNY" }})</span>
          <span class="field__control">
            <input
              v-model="form.budgetAmount"
              name="budget"
              inputmode="decimal"
              placeholder="例如：5000"
            />
          </span>
        </label>

        <label class="field">
          <span>货币</span>
          <span class="field__control">
            <input
              v-model.trim="form.currency"
              name="currency"
              maxlength="3"
              required
            />
          </span>
        </label>

        <label class="field">
          <span>节奏</span>
          <span class="field__control">
            <select v-model="form.pace" name="pace">
              <option value="relaxed">轻松</option>
              <option value="balanced">均衡</option>
              <option value="intensive">紧凑</option>
            </select>
          </span>
        </label>
      </div>

      <div class="trip-form-grid trip-form-grid--preferences">
        <label class="field field--wide">
          <span>兴趣</span>
          <span class="field__control">
            <input
              v-model="form.interests"
              name="interests"
              placeholder="美食、城市漫步、博物馆"
            />
          </span>
        </label>

        <label class="field">
          <span>交通偏好</span>
          <span class="field__control">
            <input
              v-model="form.transportPreferences"
              name="transport_preferences"
              placeholder="公共交通、步行"
            />
          </span>
        </label>

        <label class="field">
          <span>住宿偏好</span>
          <span class="field__control">
            <input
              v-model="form.lodgingPreferences"
              name="lodging_preferences"
              placeholder="市中心、安静"
            />
          </span>
        </label>

        <label class="field">
          <span>必去地点</span>
          <span class="field__control">
            <input v-model="form.mustVisit" name="must_visit" placeholder="洪崖洞" />
          </span>
        </label>

        <label class="field">
          <span>避免</span>
          <span class="field__control">
            <input v-model="form.avoid" name="avoid" placeholder="人多的时段" />
          </span>
        </label>

        <label class="field field--wide">
          <span>其他约束</span>
          <span class="field__control">
            <input
              v-model="form.constraints"
              name="constraints"
              placeholder="不吃辣、每天不超过三个景点"
            />
          </span>
        </label>
      </div>
    </section>

    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <div class="trip-form-actions">
      <button class="primary-button" type="submit" :disabled="props.submitting">
        <Save :size="16" :stroke-width="1.8" />
        {{ props.submitting ? "保存中" : props.submitLabel }}
      </button>
    </div>
  </form>
</template>
