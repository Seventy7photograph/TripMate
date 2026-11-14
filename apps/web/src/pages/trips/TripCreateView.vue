<!-- 文件说明：前端页面：TripCreateView。 -->
<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";
import { ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { tripApi } from "../../features/trips/api";
import TripBriefEditor from "../../features/trips/TripBriefEditor.vue";
import type { TripBrief } from "../../features/trips/types";
import { ApiError } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const submitting = ref(false);
const error = ref("");

async function createTrip(brief: TripBrief): Promise<void> {
  if (!auth.token) return;
  submitting.value = true;
  error.value = "";
  try {
    const trip = await tripApi.create(auth.token, { brief });
    await router.push(`/trips/${trip.id}`);
  } catch (cause) {
    error.value =
      cause instanceof ApiError && cause.status === 422
        ? "请检查日期、人数、预算和必填字段。"
        : "旅行创建失败，请稍后重试。";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="trip-editor-page">
    <header class="trip-editor-heading">
      <RouterLink class="back-link" to="/trips">
        <ArrowLeft :size="16" :stroke-width="1.8" />
        返回旅行列表
      </RouterLink>
      <h1>新建旅行</h1>
      <p>先保存旅行主数据，后续可以继续添加逐日行程。</p>
    </header>

    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <TripBriefEditor
      submit-label="创建旅行"
      :submitting="submitting"
      @submit="createTrip"
    />
  </main>
</template>
