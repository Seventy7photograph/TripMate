// 文件说明：Pinia 状态仓库：auth.test。
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "./auth";
import { useConversationStore } from "./conversation";

const TOKEN_KEY = "tripmate.access-token";
const user = {
  id: "5aa38cbc-9300-4f57-a4d1-97e33b64ea8e",
  email: "traveler@example.com",
  display_name: "Test Traveler",
  default_origin: "Shanghai",
  currency: "CNY",
  language: "zh-CN",
  created_at: "2026-11-13T12:00:00Z",
  updated_at: "2026-11-13T12:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("auth store", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("restores a valid session after refresh", async () => {
    window.sessionStorage.setItem(TOKEN_KEY, "stored-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(user)));

    const store = useAuthStore();
    await store.initialize();

    expect(store.isAuthenticated).toBe(true);
    expect(store.user?.email).toBe(user.email);
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe("stored-token");
  });

  it("stores the session after login and clears it on logout", async () => {
    const conversation = useConversationStore();
    conversation.applyConversation({
      id: "conversation-1",
      title: "重庆",
      messages: [{ id: 1, role: "user", kind: "text", text: "去重庆" }],
      requirement_history: ["去重庆"],
      planning_draft: {},
      trip_id: null,
      version: 1,
      message_count: 1,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          access_token: "new-token",
          token_type: "bearer",
          expires_in: 1800,
          user,
        }),
      ),
    );

    const store = useAuthStore();
    await store.login(user.email, "correct-horse-battery-staple");

    expect(store.isAuthenticated).toBe(true);
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe("new-token");
    expect(conversation.hasConversation).toBe(false);
    expect(
      window.sessionStorage.getItem("tripmate.active-conversation-id"),
    ).toBeNull();

    await store.logout();
    expect(store.isAuthenticated).toBe(false);
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({
        method: "POST",
        headers: expect.any(Headers),
      }),
    );
  });

  it("clears an expired stored token", async () => {
    window.sessionStorage.setItem(TOKEN_KEY, "expired-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Invalid or expired token" }, 401)),
    );

    const store = useAuthStore();
    await store.initialize();

    expect(store.isAuthenticated).toBe(false);
    expect(store.user).toBeNull();
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
