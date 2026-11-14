<!-- 文件说明：前端页面：AssistantView。 -->
<script setup lang="ts">
import { CircleAlert, LoaderCircle, Sparkles } from "lucide-vue-next";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import BriefForm from "../../features/assistant/BriefForm.vue";
import { assistantApi } from "../../features/assistant/api";
import type { RequirementParseResult } from "../../features/assistant/types";
import { tripApi } from "../../features/trips/api";
import type { TripBrief } from "../../features/trips/types";
import { ApiError } from "../../lib/http";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const text = ref("");
const result = ref<RequirementParseResult | null>(null);
const parsing = ref(false);
const submitting = ref(false);
const error = ref("");

const initialValue = computed(() => result.value?.draft ?? null);
const canParse = computed(() => text.value.trim().length > 0 && !parsing.value);

async function parseRequirements(): Promise<void> {
  if (!auth.token || !canParse.value) return;
  parsing.value = true;
  error.value = "";
  try {
    result.value = await assistantApi.parse(auth.token, text.value.trim());
  } catch (cause) {
    result.value = null;
    error.value =
      cause instanceof ApiError && cause.status === 504
        ? "模型响应超时，请稍后重试。"
        : cause instanceof ApiError && cause.status === 503
          ? "真实模型尚未配置，请联系管理员。"
          : "需求解析失败，请检查描述后重试。";
  } finally {
    parsing.value = false;
  }
}

function handleComposerKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  void parseRequirements();
}

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
  <main class="assistant-page">
    <header class="assistant-heading">
      <p class="section-kicker">AI 行程入口</p>
      <h1>把旅行想法变成可确认的需求</h1>
      <p>描述目的地、日期、同行人数、预算和偏好，TripMate 会先整理，再由你确认。</p>
    </header>

    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <div class="assistant-workspace">
      <section class="assistant-intake" aria-labelledby="assistant-intake-title">
        <header class="assistant-intake__heading">
          <span class="assistant-intake__icon" aria-hidden="true">
            <Sparkles :size="18" :stroke-width="1.8" />
          </span>
          <div>
            <h2 id="assistant-intake-title">用自然语言描述旅行</h2>
            <p>没有提到的信息不会被自动补全。</p>
          </div>
        </header>

        <label class="field assistant-intake__field">
          <span>旅行需求</span>
          <span class="field__control field__control--textarea">
            <textarea
              v-model="text"
              name="travel_requirement"
              rows="9"
              maxlength="10000"
              placeholder="例如：2026年12月1日到12月3日，我和朋友2个人从上海去重庆，预算5000元，喜欢美食和城市漫步，想轻松一点。"
              @keydown="handleComposerKeydown"
            />
          </span>
        </label>

        <div class="assistant-intake__actions">
          <button
            class="primary-button"
            type="button"
            :disabled="!canParse"
            @click="parseRequirements"
          >
            <LoaderCircle
              v-if="parsing"
              :size="16"
              :stroke-width="1.8"
              class="is-spinning"
            />
            <Sparkles v-else :size="16" :stroke-width="1.8" />
            {{ parsing ? "正在解析" : "解析旅行需求" }}
          </button>
        </div>
      </section>

      <section
        v-if="result"
        class="assistant-result"
        aria-live="polite"
        aria-labelledby="assistant-result-title"
      >
        <div
          v-if="result.questions.length > 0"
          class="assistant-questions"
          role="status"
        >
          <CircleAlert :size="19" :stroke-width="1.7" aria-hidden="true" />
          <div>
            <h2 id="assistant-result-title">还需要确认这些信息</h2>
            <ul>
              <li v-for="question in result.questions" :key="question">
                {{ question }}
              </li>
            </ul>
          </div>
        </div>
        <div v-else class="assistant-result__ready">
          <span class="assistant-result__mark" aria-hidden="true">✓</span>
          <div>
            <h2 id="assistant-result-title">需求已结构化</h2>
            <p>请检查识别结果，确认无误后创建旅行。</p>
          </div>
        </div>

        <BriefForm
          :initial-value="initialValue"
          :missing-fields="result.missing_fields"
          :submitting="submitting"
          @submit="createTrip"
        />
      </section>

      <section v-else class="assistant-empty" aria-label="等待解析">
        <Sparkles :size="26" :stroke-width="1.4" aria-hidden="true" />
        <p>解析结果会在这里展开，所有字段都可以在创建前修改。</p>
      </section>
    </div>
  </main>
</template>
