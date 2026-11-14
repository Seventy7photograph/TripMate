<!-- 文件说明：前端功能模块：ItineraryDiff。 -->
<script setup lang="ts">
import { Check, Trash2, X } from "lucide-vue-next";
import { computed } from "vue";

import type { ItineraryPatch } from "./patchTypes";

const props = defineProps<{
  patch: ItineraryPatch | null;
  applying: boolean;
  error: string;
}>();

const emit = defineEmits<{
  apply: [];
  discard: [];
  close: [];
}>();

const removedStops = computed(() => {
  if (!props.patch) return [];
  const removed = new Set(props.patch.changes.removed_stop_ids);
  return props.patch.changes.before_stops.filter((stop) => removed.has(stop.id));
});

const keptStops = computed(() => props.patch?.changes.after_stops ?? []);

function stopName(stop: { place_id: string; place_name: string | null }): string {
  return stop.place_name || stop.place_id;
}
</script>

<template>
  <Transition name="dialog-fade">
    <div
      v-if="patch"
      class="dialog-backdrop"
      role="presentation"
      @click.self="emit('close')"
    >
      <section
        class="itinerary-diff"
        role="dialog"
        aria-modal="true"
        aria-labelledby="itinerary-diff-title"
      >
        <header>
          <div>
            <h2 id="itinerary-diff-title">确认这次局部调整</h2>
            <span>{{ patch.instruction }} · {{ patch.changes.target_day_date }}</span>
          </div>
          <button class="icon-action" type="button" aria-label="关闭差异" @click="emit('close')">
            <X :size="18" :stroke-width="1.8" />
          </button>
        </header>

        <div class="itinerary-diff__summary">
          <span>{{ patch.changes.before_stop_count }} 个地点</span>
          <strong>→</strong>
          <span>{{ patch.changes.after_stop_count }} 个地点</span>
          <small>基于 v{{ patch.base_version }}，仅影响这一天</small>
        </div>

        <div class="itinerary-diff__columns">
          <section aria-labelledby="diff-removed-title">
            <h3 id="diff-removed-title">将移除</h3>
            <p v-if="removedStops.length === 0">没有移除项</p>
            <ul v-else>
              <li v-for="stop in removedStops" :key="stop.id">
                <Trash2 :size="14" :stroke-width="1.8" />
                <span>{{ stopName(stop) }}</span>
              </li>
            </ul>
          </section>
          <section aria-labelledby="diff-kept-title">
            <h3 id="diff-kept-title">保留顺序</h3>
            <p v-if="keptStops.length === 0">这一天将没有地点</p>
            <ol v-else>
              <li v-for="stop in keptStops" :key="stop.id">
                {{ stopName(stop) }}
              </li>
            </ol>
          </section>
        </div>

        <p v-if="error" class="form-error" role="alert">{{ error }}</p>

        <footer>
          <button class="quiet-action" type="button" :disabled="applying" @click="emit('discard')">
            丢弃调整
          </button>
          <button class="primary-button" type="button" :disabled="applying" @click="emit('apply')">
            <Check :size="16" :stroke-width="1.9" />
            {{ applying ? "应用中" : "确认应用" }}
          </button>
        </footer>
      </section>
    </div>
  </Transition>
</template>
