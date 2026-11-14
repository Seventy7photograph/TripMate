<!-- 文件说明：前端功能模块：AuthView。 -->
<script setup lang="ts">
import {
  ArrowLeft,
  ArrowRight,
  Compass,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { ApiError } from "./api";
import { safeAuthRedirect } from "./redirect";
import LeafActionButton from "../../components/LeafActionButton.vue";
import { useAuthStore } from "../../stores/auth";

const props = defineProps<{
  mode: "login" | "register";
}>();

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const form = reactive({
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
});
const error = ref("");
const showPassword = ref(false);
const videoSource = "/media/travel-backdrop.mp4";
const fieldErrors = reactive({
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
});

const isRegister = computed(() => props.mode === "register");
const departureChars = computed(() =>
  (auth.loading ? "出发中" : "出发").split(""),
);

function clearErrors(): void {
  error.value = "";
  fieldErrors.displayName = "";
  fieldErrors.email = "";
  fieldErrors.password = "";
  fieldErrors.confirmPassword = "";
}

watch(
  () => props.mode,
  () => {
    clearErrors();
    form.password = "";
    form.confirmPassword = "";
    showPassword.value = false;
  },
);

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 409) return "该邮箱已经注册，请直接登录。";
    if (cause.status === 401) return "邮箱或密码不正确。";
    if (cause.status === 422) return "请检查邮箱、密码和个人资料格式。";
  }
  return "请求没有完成，请稍后重试。";
}

async function submit(): Promise<void> {
  clearErrors();
  if (isRegister.value && !form.displayName) {
    fieldErrors.displayName = "请输入称呼";
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    fieldErrors.email = "请输入有效邮箱";
  }
  if (isRegister.value && form.password.length < 12) {
    fieldErrors.password = "密码至少 12 位";
  } else if (!form.password) {
    fieldErrors.password = "请输入密码";
  }
  if (isRegister.value && form.password !== form.confirmPassword) {
    fieldErrors.confirmPassword = "两次输入的密码不一致";
  }
  if (Object.values(fieldErrors).some(Boolean)) return;

  try {
    if (isRegister.value) {
      await auth.register(form.email, form.password, form.displayName);
    } else {
      await auth.login(form.email, form.password);
    }
    await router.push(safeAuthRedirect(route.query.redirect));
  } catch (cause) {
    error.value = errorMessage(cause);
  }
}
</script>

<template>
  <main class="auth-page auth-page--cinematic">
    <video
      class="auth-backdrop-video"
      autoplay
      muted
      loop
      playsinline
      aria-hidden="true"
    >
      <source :src="videoSource" type="video/mp4" />
    </video>
    <div class="auth-backdrop-overlay" aria-hidden="true" />

    <header class="auth-topbar">
      <RouterLink class="auth-wordmark" to="/">
        <span><Compass :size="18" :stroke-width="1.8" /></span>
        TripMate
      </RouterLink>
      <RouterLink class="auth-return" to="/">
        <ArrowLeft :size="15" :stroke-width="1.8" />
        返回对话
      </RouterLink>
    </header>

    <div class="auth-layout">
      <section class="auth-intro" aria-labelledby="auth-title">
        <h1 id="auth-title">
          把想去的地方，
          <span>说成一段旅程。</span>
        </h1>
      </section>

      <section class="auth-panel" aria-labelledby="auth-form-title">
        <header>
          <h2 id="auth-form-title">
            {{ isRegister ? "创建旅行工作区" : "登录 TripMate" }}
          </h2>
        </header>

        <form novalidate @submit.prevent="submit">
          <label
            v-if="isRegister"
            class="field"
            :class="{ 'has-error': fieldErrors.displayName }"
          >
            <span>称呼</span>
            <span class="field__control">
              <UserRound :size="17" :stroke-width="1.7" aria-hidden="true" />
              <input
                v-model.trim="form.displayName"
                name="display_name"
                autocomplete="name"
                maxlength="80"
                required
                placeholder="你的旅行称呼"
              />
            </span>
            <span v-if="fieldErrors.displayName" class="field-error" role="alert">
              {{ fieldErrors.displayName }}
            </span>
          </label>

          <label class="field" :class="{ 'has-error': fieldErrors.email }">
            <span>邮箱</span>
            <span class="field__control">
              <Mail :size="17" :stroke-width="1.7" aria-hidden="true" />
              <input
                v-model.trim="form.email"
                name="email"
                type="email"
                autocomplete="email"
                maxlength="320"
                required
                placeholder="you@example.com"
              />
            </span>
            <span v-if="fieldErrors.email" class="field-error" role="alert">
              {{ fieldErrors.email }}
            </span>
          </label>

          <label class="field" :class="{ 'has-error': fieldErrors.password }">
            <span>密码</span>
            <span class="field__control">
              <LockKeyhole :size="17" :stroke-width="1.7" aria-hidden="true" />
              <input
                v-model="form.password"
                name="password"
                :type="showPassword ? 'text' : 'password'"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                :minlength="isRegister ? 12 : 1"
                maxlength="128"
                required
                :placeholder="isRegister ? '至少 12 位' : '输入密码'"
              />
              <button
                class="field__icon-button"
                type="button"
                :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <EyeOff v-if="showPassword" :size="17" :stroke-width="1.7" />
                <Eye v-else :size="17" :stroke-width="1.7" />
              </button>
            </span>
            <span v-if="fieldErrors.password" class="field-error" role="alert">
              {{ fieldErrors.password }}
            </span>
          </label>

          <label
            v-if="isRegister"
            class="field"
            :class="{ 'has-error': fieldErrors.confirmPassword }"
          >
            <span>确认密码</span>
            <span class="field__control">
              <LockKeyhole :size="17" :stroke-width="1.7" aria-hidden="true" />
              <input
                v-model="form.confirmPassword"
                name="confirm_password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                minlength="12"
                maxlength="128"
                required
                placeholder="再次输入密码"
              />
            </span>
            <span
              v-if="fieldErrors.confirmPassword"
              class="field-error"
              role="alert"
            >
              {{ fieldErrors.confirmPassword }}
            </span>
          </label>

          <p v-if="error" class="form-error" role="alert">{{ error }}</p>

          <LeafActionButton
            v-if="isRegister"
            class="auth-register-submit"
            :label="auth.loading ? '处理中' : '创建账号'"
            type="submit"
            width="240px"
            :disabled="auth.loading"
          >
            <template #icon>
              <ArrowRight :size="17" :stroke-width="1.8" />
            </template>
          </LeafActionButton>
          <button
            v-else
            class="departure-button type--C"
            type="submit"
            :disabled="auth.loading"
            :aria-label="auth.loading ? '出发中' : '出发'"
          >
            <span class="button__line button__line--left" aria-hidden="true" />
            <span class="button__line button__line--right" aria-hidden="true" />
            <span class="button__text">
              <span
                v-for="(char, index) in departureChars"
                :key="`${char}-${index}`"
                class="button__char"
              >
                {{ char }}
              </span>
            </span>
            <span class="button__drow1" aria-hidden="true" />
            <span class="button__drow2" aria-hidden="true" />
          </button>
        </form>

        <p class="auth-switch">
          {{ isRegister ? "已有账号？" : "第一次使用 TripMate？" }}
          <RouterLink :to="isRegister ? '/login' : '/register'">
            {{ isRegister ? "登录" : "创建账号" }}
          </RouterLink>
        </p>
      </section>
    </div>
  </main>
</template>

<style scoped>
.type--C {
  --line_color: #00135c;
  --back_color: #defffa;
}

.auth-register-submit {
  margin: 4px auto 0;
}

.departure-button {
  position: relative;
  isolation: isolate;
  z-index: 0;
  display: block;
  width: 240px;
  max-width: 100%;
  height: 56px;
  margin: 4px auto 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--line_color);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0;
  text-decoration: none;
  transition: all 0.3s ease;
}

.button__text {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  gap: 2px;
  transition: gap 0.3s ease;
}

.button__char {
  display: inline-block;
}

.departure-button::before,
.departure-button::after,
.button__text::before,
.button__text::after {
  position: absolute;
  height: 3px;
  border-radius: 2px;
  background: var(--line_color);
  content: "";
  transition: all 0.5s ease;
}

.departure-button::before {
  top: 0;
  left: 54px;
  width: calc(100% - 56px * 2 - 16px);
}

.departure-button::after {
  top: 0;
  right: 54px;
  width: 8px;
}

.button__text::before {
  right: 54px;
  bottom: 0;
  width: calc(100% - 56px * 2 - 16px);
}

.button__text::after {
  bottom: 0;
  left: 54px;
  width: 8px;
}

.button__line {
  position: absolute;
  top: 0;
  width: 56px;
  height: 100%;
  overflow: hidden;
}

.button__line::before {
  position: absolute;
  top: 0;
  width: 150%;
  height: 100%;
  box-sizing: border-box;
  border: solid 3px var(--line_color);
  border-radius: 300px;
  content: "";
}

.button__line--left,
.button__line--left::before {
  left: 0;
}

.button__line--right,
.button__line--right::before {
  right: 0;
}

.departure-button:hover:not(:disabled)::before,
.departure-button:hover:not(:disabled) .button__text::before {
  width: 8px;
}

.departure-button:hover:not(:disabled)::after,
.departure-button:hover:not(:disabled) .button__text::after {
  width: calc(100% - 56px * 2 - 16px);
}

.departure-button:hover:not(:disabled) {
  letter-spacing: 0;
}

.departure-button:hover:not(:disabled) .button__text {
  gap: 6px;
}

.button__drow1,
.button__drow2 {
  position: absolute;
  z-index: -1;
  border-radius: 16px;
  transform-origin: 16px 16px;
}

.button__drow1 {
  top: -16px;
  left: 40px;
  width: 32px;
  height: 0;
  transform: rotate(30deg);
}

.button__drow2 {
  top: 44px;
  left: 77px;
  width: 32px;
  height: 0;
  transform: rotate(-127deg);
}

.button__drow1::before,
.button__drow1::after,
.button__drow2::before,
.button__drow2::after {
  position: absolute;
  content: "";
}

.button__drow1::before {
  bottom: 0;
  left: 0;
  width: 0;
  height: 32px;
  border-radius: 16px;
  transform: rotate(-60deg);
  transform-origin: 16px 16px;
}

.button__drow1::after {
  top: -10px;
  left: 45px;
  width: 0;
  height: 32px;
  border-radius: 16px;
  transform: rotate(69deg);
  transform-origin: 16px 16px;
}

.button__drow2::before {
  bottom: 0;
  left: 0;
  width: 0;
  height: 32px;
  border-radius: 16px;
  transform: rotate(-146deg);
  transform-origin: 16px 16px;
}

.button__drow2::after {
  bottom: 26px;
  left: -40px;
  width: 0;
  height: 32px;
  border-radius: 16px;
  transform: rotate(-262deg);
  transform-origin: 16px 16px;
}

.button__drow1,
.button__drow1::before,
.button__drow1::after,
.button__drow2,
.button__drow2::before,
.button__drow2::after {
  background: var(--back_color);
}

.departure-button:hover:not(:disabled) .button__drow1 {
  animation: drow1 0.06s ease-in forwards;
}

.departure-button:hover:not(:disabled) .button__drow1::before {
  animation: drow2 0.08s linear 0.06s forwards;
}

.departure-button:hover:not(:disabled) .button__drow1::after {
  animation: drow3 0.03s linear 0.14s forwards;
}

.departure-button:hover:not(:disabled) .button__drow2 {
  animation: drow4 0.06s linear 0.2s forwards;
}

.departure-button:hover:not(:disabled) .button__drow2::before {
  animation: drow3 0.03s linear 0.26s forwards;
}

.departure-button:hover:not(:disabled) .button__drow2::after {
  animation: drow5 0.06s linear 0.32s forwards;
}

@keyframes drow1 {
  from { height: 0; }
  to { height: 100px; }
}

@keyframes drow2 {
  0% { width: 0; opacity: 0; }
  10% { opacity: 0; }
  11% { opacity: 1; }
  100% { width: 120px; }
}

@keyframes drow3 {
  from { width: 0; }
  to { width: 80px; }
}

@keyframes drow4 {
  from { height: 0; }
  to { height: 120px; }
}

@keyframes drow5 {
  from { width: 0; }
  to { width: 124px; }
}

.departure-button:focus-visible {
  outline: 2px solid var(--line_color);
  outline-offset: 4px;
}

.departure-button:disabled {
  cursor: wait;
}

@media (prefers-reduced-motion: reduce) {
  .departure-button,
  .departure-button::before,
  .departure-button::after,
  .button__text,
  .button__text::before,
  .button__text::after,
  .button__drow1,
  .button__drow2 {
    animation: none;
    transition: none;
  }
}
</style>
