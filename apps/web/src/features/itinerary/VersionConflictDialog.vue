<!-- 文件说明：前端功能模块：VersionConflictDialog。 -->
<script setup lang="ts">
import {
  Copy,
  GitCompareArrows,
  RefreshCw,
  X,
} from "lucide-vue-next";

withDefaults(
  defineProps<{
    open: boolean;
    currentVersion: number;
    localLabel: string;
    copyStatus: string;
    applying: boolean;
  }>(),
  {
    copyStatus: "",
    applying: false,
  },
);

const emit = defineEmits<{
  "keep-local": [];
  "load-server": [];
  "copy-diff": [];
  close: [];
}>();
</script>

<template>
  <div
    v-if="open"
    class="dialog-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="conflict-title"
  >
    <section class="conflict-dialog">
      <header>
        <span class="dialog-icon">
          <GitCompareArrows :size="21" :stroke-width="1.7" />
        </span>
        <div>
          <p>Version conflict</p>
          <h2 id="conflict-title">这份旅行已在别处更新</h2>
        </div>
        <button class="icon-action" type="button" aria-label="关闭冲突提示" @click="emit('close')">
          <X :size="17" :stroke-width="1.8" />
        </button>
      </header>

      <div class="conflict-dialog__body">
        <p>
          服务端当前版本为 <strong>v{{ currentVersion }}</strong>。本地改动
          <strong>{{ localLabel }}</strong>
          尚未覆盖服务端数据，请选择保留哪一份。
        </p>
        <div class="conflict-dialog__choices">
          <div>
            <strong>保留本地</strong>
            <span>以当前服务端版本为基线再次提交本地改动。</span>
          </div>
          <div>
            <strong>载入服务端</strong>
            <span>放弃本地草稿，重新加载最新旅行与行程。</span>
          </div>
        </div>
      </div>

      <footer>
        <button class="quiet-action" type="button" @click="emit('copy-diff')">
          <Copy :size="15" :stroke-width="1.8" />
          {{ copyStatus || "复制差异" }}
        </button>
        <button
          class="quiet-action"
          type="button"
          :disabled="applying"
          @click="emit('load-server')"
        >
          <RefreshCw :size="15" :stroke-width="1.8" />
          载入服务端
        </button>
        <button
          class="primary-button"
          type="button"
          :disabled="applying"
          @click="emit('keep-local')"
        >
          {{ applying ? "提交中" : "保留本地" }}
        </button>
      </footer>
    </section>
  </div>
</template>
