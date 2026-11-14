// 文件说明：前端页面：HomeView.test。
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { travelChatApi } from "../features/chat/agentApi";
import { conversationApi } from "../features/chat/api";
import { itineraryApi } from "../features/itinerary/api";
import { planningApi } from "../features/planning/api";
import { tripApi } from "../features/trips/api";
import ChatAttachmentPicker from "../features/upload/ChatAttachmentPicker.vue";
import { uploadApi } from "../features/upload/api";
import { useConversationStore } from "../stores/conversation";
import HomeView from "./HomeView.vue";

const { routerPush } = vi.hoisted(() => ({
  routerPush: vi.fn(),
}));

vi.mock("../features/chat/agentApi", () => ({
  travelChatApi: {
    respond: vi.fn(),
  },
}));

vi.mock("../features/trips/api", () => ({
  tripApi: {
    create: vi.fn(),
  },
}));

vi.mock("../features/planning/api", () => ({
  planningApi: {
    start: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock("../features/itinerary/api", () => ({
  itineraryApi: {
    get: vi.fn(),
  },
}));

vi.mock("../features/chat/api", () => ({
  conversationApi: {
    create: vi.fn(),
    update: vi.fn(),
    list: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock("../features/upload/api", () => ({
  uploadApi: {
    upload: vi.fn(),
    remove: vi.fn(),
  },
}));

vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" },
  useRoute: () => ({ fullPath: "/", query: {} }),
  useRouter: () => ({ push: routerPush }),
}));

const brief = {
  destination: "重庆",
  origin: "上海",
  start_date: "2026-12-01",
  end_date: "2026-12-03",
  party_size: 2,
  budget_minor: 500_000,
  currency: "CNY",
  interests: ["美食"],
  pace: "balanced" as const,
  transport_preferences: [],
  lodging_preferences: [],
  must_visit: [],
  avoid: [],
  constraints: [],
};

describe("HomeView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setActivePinia(createPinia());
    sessionStorage.clear();
    sessionStorage.setItem("tripmate.access-token", "token");
    vi.mocked(conversationApi.list).mockResolvedValue({ items: [] });
    vi.mocked(conversationApi.create).mockResolvedValue({
      id: "conversation-1",
      title: "重庆",
      messages: [],
      requirement_history: [],
      trip_id: null,
      version: 1,
      message_count: 0,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("renders the Chinese conversation-first home", () => {
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    expect(wrapper.get("h1").text()).toBe("新的故事，从哪里开始？");
    expect(wrapper.get("textarea").attributes("placeholder")).toContain(
      "2026年12月1日",
    );
    expect(wrapper.text()).not.toContain("Ctrl + Enter");
    expect(
      wrapper.findAll("button").some((button) => button.text().includes("历史对话")),
    ).toBe(true);
    expect(wrapper.get(".flower-action").text()).toContain("开始规划");
  });

  it("renders a cached conversation immediately after remount", () => {
    const conversation = useConversationStore();
    conversation.applyConversation({
      id: "conversation-1",
      title: "重庆",
      messages: [
        { id: 1, role: "user", kind: "text", text: "去重庆" },
        {
          id: 2,
          role: "assistant",
          kind: "plan",
          text: "已生成",
          trip: {
            id: "trip-1",
            owner_id: "user-1",
            status: "draft",
            version: 1,
            brief,
            created_at: "2026-11-14T00:00:00Z",
            updated_at: "2026-11-14T00:00:00Z",
          },
        },
      ],
      requirement_history: ["去重庆"],
      trip_id: "trip-1",
      version: 2,
      message_count: 2,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });

    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    expect(wrapper.text()).toContain("去重庆");
    expect(wrapper.text()).not.toContain("新的故事，从哪里开始？");
    expect(wrapper.get(".flower-action").text()).toContain("发送");
  });

  it("starts a new conversation even when saved history exists", async () => {
    vi.mocked(conversationApi.list).mockResolvedValue({
      items: [
        {
          id: "conversation-1",
          title: "重庆",
          preview: "去重庆",
          trip_id: "trip-1",
          version: 2,
          message_count: 2,
          updated_at: "2026-11-14T00:00:00Z",
        },
      ],
    });

    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(wrapper.get("h1").text()).toBe("新的故事，从哪里开始？");
    expect(wrapper.text()).not.toContain("去重庆");
    expect(conversationApi.get).not.toHaveBeenCalled();
  });

  it("restores only the explicitly active conversation after refresh", async () => {
    sessionStorage.setItem("tripmate.active-conversation-id", "conversation-1");
    vi.mocked(conversationApi.list).mockResolvedValue({
      items: [
        {
          id: "conversation-1",
          title: "重庆",
          preview: "去重庆",
          trip_id: null,
          version: 2,
          message_count: 1,
          updated_at: "2026-11-14T00:00:00Z",
        },
      ],
    });
    vi.mocked(conversationApi.get).mockResolvedValue({
      id: "conversation-1",
      title: "重庆",
      messages: [{ id: 1, role: "user", kind: "text", text: "去重庆" }],
      requirement_history: ["去重庆"],
      trip_id: null,
      version: 2,
      message_count: 1,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });

    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(conversationApi.get).toHaveBeenCalledWith("token", "conversation-1");
    expect(wrapper.text()).toContain("去重庆");
  });

  it("does not restore the latest history after returning from another menu", async () => {
    vi.mocked(conversationApi.list).mockResolvedValue({
      items: [
        {
          id: "conversation-old",
          title: "旧对话",
          preview: "上次旅行",
          trip_id: null,
          version: 2,
          message_count: 1,
          updated_at: "2026-11-14T00:00:00Z",
        },
      ],
    });
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();
    wrapper.unmount();

    const remounted = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(remounted.get("h1").text()).toBe("新的故事，从哪里开始？");
    expect(conversationApi.get).not.toHaveBeenCalled();
  });

  it("keeps missing requirements in the conversation", async () => {
    vi.mocked(travelChatApi.respond).mockResolvedValue({
      intent: "clarify",
      in_scope: true,
      confidence: 0.9,
      answer: null,
      sources: [],
      selected_skills: [],
      used_tools: [],
      requires_planning: false,
      brief: null,
      draft: {
        destination: "重庆",
        start_date: "2026-12-01",
        end_date: "2026-12-03",
        party_size: 2,
      },
      missing_fields: ["budget_minor"],
      questions: ["这次旅行的总预算大约是多少？"],
      model_name: "mock-tripbrief-v1",
    });
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    await wrapper
      .get("textarea")
      .setValue("2026年12月1日到12月3日，2个人从上海去重庆，喜欢美食。");
    const submitting = wrapper.get("form").trigger("submit");
    await vi.advanceTimersByTimeAsync(240);
    await submitting;
    await flushPromises();

    expect(travelChatApi.respond).toHaveBeenCalledWith(
      "token",
      "2026年12月1日到12月3日，2个人从上海去重庆，喜欢美食。",
      [],
      [],
    );
    expect(wrapper.text()).toContain("这次旅行的总预算大约是多少？");
    expect(wrapper.text()).toContain("重庆");
  });

  it("uploads an attachment and passes its id to requirement parsing", async () => {
    vi.mocked(travelChatApi.respond).mockResolvedValue({
      intent: "clarify",
      in_scope: true,
      confidence: 0.8,
      answer: null,
      sources: [],
      selected_skills: [],
      used_tools: [],
      requires_planning: false,
      brief: null,
      draft: { destination: "重庆" },
      missing_fields: ["start_date"],
      questions: ["请提供具体日期。"],
      model_name: "mock-tripbrief-v1",
    });
    vi.mocked(uploadApi.upload).mockResolvedValue({
      id: "asset-1",
      name: "行程截图.png",
      mime_type: "image/png",
      kind: "image",
      size_bytes: 128,
      created_at: "2026-11-14T00:00:00Z",
      expires_at: "2026-11-15T00:00:00Z",
    });
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    const file = new File([new Uint8Array([1, 2, 3])], "行程截图.png", {
      type: "image/png",
    });
    wrapper.findComponent(ChatAttachmentPicker).vm.$emit("update:attachments", [
      {
        key: "local-1",
        file,
        previewUrl: null,
      },
    ]);
    await wrapper.get("textarea").setValue("根据附件识别需求");
    const submitting = wrapper.get("form").trigger("submit");
    await vi.advanceTimersByTimeAsync(240);
    await submitting;
    await flushPromises();

    expect(uploadApi.upload).toHaveBeenCalledWith("token", file);
    expect(travelChatApi.respond).toHaveBeenCalledWith(
      "token",
      "根据附件识别需求",
      ["asset-1"],
      [],
    );
    expect(wrapper.text()).toContain("行程截图.png");
  });

  it("renders a sourced travel answer with folded citations", async () => {
    vi.mocked(travelChatApi.respond).mockResolvedValue({
      intent: "destination_research",
      in_scope: true,
      confidence: 0.95,
      answer: "开元寺是泉州古城的重要古建。",
      sources: [
        {
          url: "https://example.com/quanzhou",
          title: "泉州文旅",
        },
      ],
      selected_skills: ["destination-research"],
      used_tools: ["search_places"],
      requires_planning: false,
      brief: null,
      draft: null,
      missing_fields: [],
      questions: [],
      model_name: "deepseek-flash",
    });
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    await wrapper.get("textarea").setValue("泉州开元寺有什么值得看的？");
    const submitting = wrapper.get("form").trigger("submit");
    await vi.advanceTimersByTimeAsync(240);
    await submitting;
    await flushPromises();

    expect(wrapper.text()).toContain("开元寺是泉州古城的重要古建。");
    expect(wrapper.get(".agent-sources summary").text()).toContain("引用来源");
    expect(wrapper.get(".agent-sources a").text()).toContain("泉州文旅");
    expect(tripApi.create).not.toHaveBeenCalled();
  });

  it("creates and renders a linked itinerary from a complete brief", async () => {
    vi.mocked(travelChatApi.respond).mockResolvedValue({
      intent: "plan_trip",
      in_scope: true,
      confidence: 0.95,
      answer: "旅行需求已整理完成，可以开始生成行程。",
      sources: [],
      selected_skills: [],
      used_tools: [],
      requires_planning: true,
      brief,
      draft: brief,
      missing_fields: [],
      questions: [],
      model_name: "mock-tripbrief-v1",
    });
    vi.mocked(tripApi.create).mockResolvedValue({
      id: "trip-1",
      owner_id: "user-1",
      status: "draft",
      version: 1,
      brief,
      created_at: "2026-11-14T00:00:00Z",
      updated_at: "2026-11-14T00:00:00Z",
    });
    vi.mocked(planningApi.start).mockResolvedValue({
      job_id: "job-1",
      status: "running",
    });
    vi.mocked(planningApi.get).mockResolvedValue({
      id: "job-1",
      trip_id: "trip-1",
      status: "completed",
      progress: 100,
      events: [],
      result: {
        trip_id: "trip-1",
        version: 1,
        validation_summary: [],
        days: [
          {
            id: "day-1",
            date: "2026-12-01",
            theme: "城市初见",
            stops: [
              {
                id: "stop-1",
                place_id: "place-1",
                place_name: "洪崖洞",
                start_at: "2026-12-01T09:00:00",
                duration_minutes: 90,
                estimated_cost_minor: 5_000,
                source: {
                  provider: "mock",
                  provider_place_id: "place-1",
                  source_url: null,
                  queried_at: "2026-11-14T00:00:00Z",
                  freshness: "mock",
                  confidence: 1,
                },
              },
            ],
          },
        ],
      },
      error_code: null,
      error_message: null,
      created_at: "2026-11-14T00:00:00Z",
      started_at: "2026-11-14T00:00:00Z",
      finished_at: "2026-11-14T00:00:01Z",
      tool_call_count: 4,
      loop_count: 0,
    });
    vi.mocked(itineraryApi.get).mockResolvedValue({
      trip_id: "trip-1",
      version: 2,
      days: [
        {
          id: "day-real-1",
          trip_id: "trip-1",
          date: "2026-12-01",
          day_index: 1,
          theme: "城市初见",
          leg_modes: [],
          stops: [],
          created_at: "2026-11-14T00:00:00Z",
          updated_at: "2026-11-14T00:00:00Z",
        },
      ],
    });
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    await wrapper
      .get("textarea")
      .setValue("2026年12月1日到12月3日，2个人从上海去重庆，预算5000元。");
    const submitting = wrapper.get("form").trigger("submit");
    await vi.advanceTimersByTimeAsync(240);
    await submitting;
    await flushPromises();
    await flushPromises();

    expect(tripApi.create).toHaveBeenCalledWith("token", { brief });
    expect(planningApi.start).toHaveBeenCalledWith("token", "trip-1", 1, true);
    expect(wrapper.text()).toContain("已生成");
    expect(wrapper.text()).toContain("洪崖洞");
    expect(wrapper.text()).toContain("全屏地图");
  });

  it("asks a guest to log in before focusing the composer and preserves the draft", async () => {
    sessionStorage.removeItem("tripmate.access-token");
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });

    await wrapper.get("textarea").trigger("pointerdown");
    const dialog = wrapper.get('[role="dialog"]');
    expect(dialog.text()).toContain("登录后开始规划");

    await wrapper.get("textarea").setValue("泉州三天看古城");
    await wrapper.get('[role="dialog"] .guest-login-confirm').trigger("click");
    expect(sessionStorage.getItem("tripmate.guest-prompt-draft")).toBe(
      "泉州三天看古城",
    );
    expect(routerPush).toHaveBeenCalledWith({
      name: "login",
      query: { redirect: "/" },
    });
  });

  it("restores a saved guest draft after login", async () => {
    sessionStorage.setItem(
      "tripmate.guest-prompt-draft",
      "登录后继续这段旅行需求",
    );

    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(wrapper.get("textarea").element.value).toBe(
      "登录后继续这段旅行需求",
    );
    expect(
      sessionStorage.getItem("tripmate.guest-prompt-draft"),
    ).toBeNull();
  });
});
