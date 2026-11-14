<!-- 文件说明：管理后台模块：App。 -->
<script setup lang="ts">
import {
  Activity,
  Bot,
  Blocks,
  Coins,
  LogOut,
  Server,
  ShieldCheck,
} from "lucide-vue-next";
import { computed, markRaw, onMounted, ref } from "vue";

import { adminApi, ApiError } from "./api";
import AdminLogin from "./pages/AdminLogin.vue";
import AgentRuns from "./pages/AgentRuns.vue";
import Costs from "./pages/Costs.vue";
import Dashboard from "./pages/Dashboard.vue";
import Models from "./pages/Models.vue";
import Providers from "./pages/Providers.vue";
import Skills from "./pages/Skills.vue";
import type { AdminUser } from "./types";

const TOKEN_KEY = "tripmate.admin-token";
const token = ref<string | null>(window.sessionStorage.getItem(TOKEN_KEY));
const user = ref<AdminUser | null>(null);
const ready = ref(false);
const loggingIn = ref(false);
const loginError = ref("");
const activePage = ref<PageKey>("dashboard");

const pages = {
  dashboard: markRaw(Dashboard),
  runs: markRaw(AgentRuns),
  providers: markRaw(Providers),
  skills: markRaw(Skills),
  models: markRaw(Models),
  costs: markRaw(Costs),
} as const;

type PageKey = keyof typeof pages;

const navigation = [
  { key: "dashboard", label: "概览", icon: Activity },
  { key: "runs", label: "Agent Runs", icon: ShieldCheck },
  { key: "providers", label: "Provider", icon: Server },
  { key: "skills", label: "Skills", icon: Blocks },
  { key: "models", label: "模型配置", icon: Bot },
  { key: "costs", label: "成本", icon: Coins },
] as const;

const activeComponent = computed(() => pages[activePage.value]);
const initials = computed(() => {
  const name = user.value?.display_name.trim();
  return name ? name.slice(0, 2).toUpperCase() : "AD";
});

function clearSession(): void {
  token.value = null;
  user.value = null;
  window.sessionStorage.removeItem(TOKEN_KEY);
}

async function initialize(): Promise<void> {
  if (!token.value) {
    ready.value = true;
    return;
  }
  try {
    const profile = await adminApi.me(token.value);
    if (profile.role !== "admin") throw new ApiError(403, "该账号没有管理权限");
    user.value = profile;
  } catch {
    clearSession();
  } finally {
    ready.value = true;
  }
}

async function login(email: string, password: string): Promise<void> {
  loggingIn.value = true;
  loginError.value = "";
  try {
    const session = await adminApi.login(email, password);
    token.value = session.access_token;
    user.value = session.user;
    window.sessionStorage.setItem(TOKEN_KEY, session.access_token);
  } catch (cause) {
    loginError.value =
      cause instanceof ApiError && cause.status === 403
        ? "该账号没有管理权限。"
        : cause instanceof ApiError && cause.status === 401
          ? "邮箱或密码不正确。"
          : "登录失败，请稍后重试。";
  } finally {
    loggingIn.value = false;
  }
}

function logout(): void {
  clearSession();
  activePage.value = "dashboard";
}

onMounted(initialize);
</script>

<template>
  <div v-if="!ready" class="admin-boot">
    <span>TripMate Admin</span>
  </div>

  <AdminLogin
    v-else-if="!user || !token"
    :loading="loggingIn"
    :error="loginError"
    @login="login"
  />

  <el-container v-else class="admin-shell">
    <el-header class="admin-header">
      <div class="admin-brand">
        <a class="admin-wordmark" href="/" aria-label="TripMate 管理后台首页">
          TripMate
        </a>
        <span class="admin-brand__context">Admin</span>
      </div>

      <nav class="admin-nav" aria-label="管理后台导航">
        <button
          v-for="item in navigation"
          :key="item.key"
          type="button"
          :class="{ 'is-active': activePage === item.key }"
          @click="activePage = item.key"
        >
          <component :is="item.icon" :size="15" />
          {{ item.label }}
        </button>
      </nav>

      <div class="admin-header__meta">
        <span class="admin-identity">
          <span>{{ initials }}</span>
          <small>{{ user.email }}</small>
        </span>
        <button
          class="admin-icon-button"
          type="button"
          aria-label="退出管理后台"
          @click="logout"
        >
          <LogOut :size="16" />
        </button>
      </div>
    </el-header>

    <el-main class="admin-main">
      <component :is="activeComponent" :token="token" />
    </el-main>
  </el-container>
</template>
