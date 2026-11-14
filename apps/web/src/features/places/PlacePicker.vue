<!-- 文件说明：前端功能模块：PlacePicker。 -->
<script setup lang="ts">
import { LoaderCircle, MapPin, Search } from "lucide-vue-next";
import { ref } from "vue";

import { placeApi } from "./api";
import type { Place } from "./types";

const props = defineProps<{
  token: string;
  city?: string;
  placeholder?: string;
}>();

const emit = defineEmits<{
  select: [place: Place];
}>();

const query = ref("");
const results = ref<Place[]>([]);
const searching = ref(false);
const error = ref("");
const searched = ref(false);

async function search(): Promise<void> {
  const value = query.value.trim();
  if (!value || !props.token || searching.value) return;
  searching.value = true;
  searched.value = true;
  error.value = "";
  results.value = [];
  try {
    const response = await placeApi.search(props.token, {
      query: value,
      city: props.city || undefined,
      limit: 8,
    });
    results.value = response.results;
  } catch {
    error.value = "地点检索失败，请检查 Provider 配置或稍后重试。";
  } finally {
    searching.value = false;
  }
}

function select(place: Place): void {
  emit("select", place);
  query.value = place.name;
  results.value = [];
  error.value = "";
}
</script>

<template>
  <div class="place-picker">
    <div class="place-picker__search">
      <label class="field">
        <span>搜索地点</span>
        <span class="field__control">
          <Search :size="16" :stroke-width="1.7" />
          <input
            v-model.trim="query"
            :placeholder="placeholder || '输入景点、餐厅或地址'"
            maxlength="120"
            @keydown.enter.prevent="search"
          />
        </span>
      </label>
      <button class="quiet-action" type="button" :disabled="searching" @click="search">
        <LoaderCircle
          v-if="searching"
          :size="15"
          :stroke-width="1.8"
          class="is-spinning"
        />
        <Search v-else :size="15" :stroke-width="1.8" />
        {{ searching ? "检索中" : "搜索" }}
      </button>
    </div>

    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-else-if="searched && !searching && results.length === 0" class="place-picker__empty">
      没有找到匹配地点
    </p>
    <div v-if="results.length" class="place-picker__results">
      <button
        v-for="place in results"
        :key="place.provider_place_id"
        type="button"
        @click="select(place)"
      >
        <MapPin :size="15" :stroke-width="1.7" />
        <span>
          <strong>{{ place.name }}</strong>
          <small>{{ place.address || place.category || place.source.provider }}</small>
        </span>
        <small v-if="place.location">{{ place.location.coordinate_system }}</small>
      </button>
    </div>
  </div>
</template>
