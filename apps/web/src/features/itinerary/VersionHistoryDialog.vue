<!-- 文件说明：前端功能模块：VersionHistoryDialog。 -->
<script setup lang="ts">
import { History, RotateCcw, X } from "lucide-vue-next";

import type { TripVersionHistory } from "../trips/types";

defineProps<{
  open: boolean;
  loading: boolean;
  error: string;
  history: TripVersionHistory | null;
  restoringVersion: number | null;
}>();

const emit = defineEmits<{
  close: [];
  restore: [version: number];
}>();

function dayCount(version: { snapshot: { days: unknown[] } }): number {
  return version.snapshot.days.length;
}

function stopCount(version: { snapshot: { days: unknown[] } }): number {
  return version.snapshot.days.reduce<number>((total, day) => {
    if (typeof day !== "object" || day === null || !("stops" in day)) return total;
    return total + (Array.isArray(day.stops) ? day.stops.length : 0);
  }, 0);
}
</script>

<template>
  <div
    v-if="open"
    class="dialog-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="history-title"
  >
    <section class="history-dialog">
      <header>
        <span class="dialog-icon">
          <History :size="21" :stroke-width="1.7" />
        </span>
        <div>
          <p>Trip versions</p>
          <h2 id="history-title">版本历史</h2>
        </div>
        <button class="icon-action" type="button" aria-label="关闭版本历史" @click="emit('close')">
          <X :size="17" :stroke-width="1.8" />
        </button>
      </header>

      <div class="history-dialog__body">
        <p v-if="loading" class="history-dialog__state">正在加载版本快照</p>
        <p v-else-if="error" class="form-error" role="alert">{{ error }}</p>
        <p v-else-if="!history?.versions.length" class="history-dialog__state">
          暂无版本记录
        </p>

        <ol v-else class="version-list">
          <li v-for="version in [...history.versions].reverse()" :key="version.version">
            <span class="version-list__number">v{{ version.version }}</span>
            <span class="version-list__meta">
              <strong>
                {{ dayCount(version) }} 天 · {{ stopCount(version) }} 个地点
              </strong>
              <small>
                {{ new Date(version.created_at).toLocaleString("zh-CN") }}
              </small>
            </span>
            <span
              v-if="version.version === history.current_version"
              class="version-list__current"
            >
              当前
            </span>
            <button
              v-else
              class="quiet-action"
              type="button"
              :disabled="restoringVersion !== null"
              @click="emit('restore', version.version)"
            >
              <RotateCcw :size="15" :stroke-width="1.8" />
              {{ restoringVersion === version.version ? "恢复中" : "恢复此版本" }}
            </button>
          </li>
        </ol>
      </div>
    </section>
  </div>
</template>
