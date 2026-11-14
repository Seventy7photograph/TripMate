<!-- 文件说明：前端功能模块：BriefForm。 -->
<script setup lang="ts">
import TripBriefEditor from "../trips/TripBriefEditor.vue";
import type { TripBrief } from "../trips/types";

withDefaults(
  defineProps<{
    initialValue?: Partial<TripBrief> | null;
    missingFields?: string[];
    submitting?: boolean;
  }>(),
  {
    initialValue: null,
    missingFields: () => [],
    submitting: false,
  },
);

const emit = defineEmits<{
  submit: [brief: TripBrief];
}>();
</script>

<template>
  <section class="assistant-confirmation" aria-labelledby="assistant-confirmation-title">
    <header class="assistant-confirmation__heading">
      <div>
        <p class="section-kicker">确认结果</p>
        <h2 id="assistant-confirmation-title">修正 AI 识别出的旅行需求</h2>
      </div>
      <span v-if="missingFields.length > 0" class="assistant-missing-count">
        {{ missingFields.length }} 项待补充
      </span>
    </header>

    <TripBriefEditor
      :initial-value="initialValue"
      :submitting="submitting"
      submit-label="确认并创建旅行"
      @submit="emit('submit', $event)"
    />
  </section>
</template>
