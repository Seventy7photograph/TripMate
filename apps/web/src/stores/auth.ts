// 文件说明：Pinia 状态仓库：auth。
import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { authApi } from "../features/auth/api";
import type { AuthSession, ProfileUpdate, UserProfile } from "../features/auth/types";
import {
  ACTIVE_CONVERSATION_KEY,
  useConversationStore,
} from "./conversation";

const TOKEN_KEY = "tripmate.access-token";

function readStoredToken(): string | null {
  return typeof window === "undefined" ? null : window.sessionStorage.getItem(TOKEN_KEY);
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(readStoredToken());
  const user = ref<UserProfile | null>(null);
  const initialized = ref(false);
  const loading = ref(false);
  let initialization: Promise<void> | null = null;

  const isAuthenticated = computed(() => Boolean(token.value && user.value));
  const initials = computed(() => {
    const name = user.value?.display_name.trim();
    if (!name) return "TM";
    const parts = name.split(/\s+/);
    if (parts.length > 1) {
      return `${parts[0]?.[0] ?? ""}${parts.at(-1)?.[0] ?? ""}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  });

  function persistToken(nextToken: string | null): void {
    token.value = nextToken;
    if (typeof window === "undefined") return;
    if (nextToken) {
      window.sessionStorage.setItem(TOKEN_KEY, nextToken);
    } else {
      window.sessionStorage.removeItem(TOKEN_KEY);
    }
  }

  function applySession(session: AuthSession): void {
    persistToken(session.access_token);
    user.value = session.user;
  }

  function clearSession(): void {
    // 退出时同时清理身份状态和对话快照。
    useConversationStore().resetAll();
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    }
    persistToken(null);
    user.value = null;
  }

  async function initialize(): Promise<void> {
    if (initialized.value) return;
    if (initialization) return initialization;

    initialization = (async () => {
      if (!token.value) {
        initialized.value = true;
        return;
      }
      // sessionStorage 可跨刷新保留，必须先向后端验证 Token 再信任。
      try {
        user.value = await authApi.me(token.value);
      } catch {
        clearSession();
      } finally {
        initialized.value = true;
        initialization = null;
      }
    })();

    return initialization;
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true;
    try {
      const session = await authApi.login({ email, password });
      // 禁止把上一个账号的缓存对话带入新登录会话。
      useConversationStore().resetAll();
      window.sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY);
      applySession(session);
      initialized.value = true;
    } finally {
      loading.value = false;
    }
  }

  async function register(
    email: string,
    password: string,
    displayName: string,
  ): Promise<void> {
    loading.value = true;
    try {
      const session = await authApi.register({
        email,
        password,
        display_name: displayName,
      });
      useConversationStore().resetAll();
      window.sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY);
      applySession(session);
      initialized.value = true;
    } finally {
      loading.value = false;
    }
  }

  async function updateProfile(input: ProfileUpdate): Promise<void> {
    if (!token.value) throw new Error("Not authenticated");
    loading.value = true;
    try {
      user.value = await authApi.updateProfile(token.value, input);
    } finally {
      loading.value = false;
    }
  }

  function logout(): void {
    clearSession();
    initialized.value = true;
  }

  return {
    token,
    user,
    initialized,
    loading,
    isAuthenticated,
    initials,
    initialize,
    login,
    register,
    updateProfile,
    logout,
  };
});
