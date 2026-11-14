<!-- 文件说明：前端功能模块：ProfileView。 -->
<script setup lang="ts">
import { Brain, LogOut, Save, X } from "lucide-vue-next";
import { reactive, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { ApiError } from "./api";
import { useAuthStore } from "../../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const form = reactive({
  display_name: auth.user?.display_name ?? "",
  default_origin: auth.user?.default_origin ?? "",
  currency: auth.user?.currency ?? "CNY",
  language: auth.user?.language ?? "zh-CN",
});
const message = ref("");
const error = ref("");
const logoutOpen = ref(false);

async function save(): Promise<void> {
  message.value = "";
  error.value = "";
  try {
    await auth.updateProfile({
      display_name: form.display_name,
      default_origin: form.default_origin || null,
      currency: form.currency,
      language: form.language,
    });
    message.value = "个人资料已保存";
  } catch (cause) {
    error.value =
      cause instanceof ApiError && cause.status === 422
        ? "请检查资料格式。"
        : "保存失败，请稍后重试。";
  }
}

async function logout(): Promise<void> {
  auth.logout();
  logoutOpen.value = false;
  await router.push("/login");
}
</script>

<template>
  <main class="profile-page">
    <header class="profile-heading">
      <div>
        <p>Travel profile</p>
        <h1>个人资料</h1>
      </div>
      <div class="profile-heading__actions">
        <RouterLink class="quiet-action" to="/settings/memory">
          <Brain :size="16" :stroke-width="1.8" />
          旅行记忆
        </RouterLink>
        <button
          class="quiet-action profile-logout"
          type="button"
          @click="logoutOpen = true"
        >
          <LogOut :size="16" :stroke-width="1.8" />
          退出登录
        </button>
      </div>
    </header>

    <div class="profile-layout">
      <section class="profile-identity">
        <span class="profile-identity__avatar">{{ auth.initials }}</span>
        <div>
          <strong>{{ auth.user?.display_name }}</strong>
          <span>{{ auth.user?.email }}</span>
        </div>
      </section>

      <form class="profile-form" @submit.prevent="save">
        <label class="field">
          <span>称呼</span>
          <span class="field__control">
            <input v-model.trim="form.display_name" maxlength="80" required />
          </span>
        </label>

        <label class="field">
          <span>默认出发地</span>
          <span class="field__control">
            <input v-model.trim="form.default_origin" maxlength="120" placeholder="例如：上海" />
          </span>
        </label>

        <div class="profile-form__row">
          <label class="field">
            <span>货币</span>
            <span class="field__control">
              <select v-model="form.currency">
                <option value="CNY">CNY</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="JPY">JPY</option>
              </select>
            </span>
          </label>

          <label class="field">
            <span>语言</span>
            <span class="field__control">
              <select v-model="form.language">
                <option value="zh-CN">简体中文</option>
                <option value="en-US">English</option>
              </select>
            </span>
          </label>
        </div>

        <p v-if="message" class="form-success" role="status">{{ message }}</p>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>

        <button class="primary-button profile-save" type="submit" :disabled="auth.loading">
          <Save :size="16" :stroke-width="1.8" />
          {{ auth.loading ? "保存中" : "保存资料" }}
        </button>
      </form>
    </div>

    <Transition name="dialog-fade">
      <div
        v-if="logoutOpen"
        class="dialog-backdrop"
        role="presentation"
        @click.self="logoutOpen = false"
      >
        <section
          class="confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="logout-title"
        >
          <header>
            <div>
              <h2 id="logout-title">退出当前账号？</h2>
            </div>
            <button
              class="icon-action"
              type="button"
              aria-label="关闭退出确认"
              @click="logoutOpen = false"
            >
              <X :size="18" :stroke-width="1.8" />
            </button>
          </header>
          <p>退出后清除本机登录信息，服务端旅行与历史对话保留。</p>
          <footer>
            <button class="quiet-action" type="button" @click="logoutOpen = false">
              继续使用
            </button>
            <button class="primary-button" type="button" @click="logout">
              <LogOut :size="15" :stroke-width="1.8" />
              确认退出
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </main>
</template>
