// 文件说明：前端页面：MemoryView.test。
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { memoryApi } from "../../features/memory/api";
import type { TravelMemory } from "../../features/memory/types";
import { useAuthStore } from "../../stores/auth";
import MemoryView from "./MemoryView.vue";

vi.mock("../../features/memory/api", () => ({
  memoryApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    clear: vi.fn(),
  },
}));

const memory: TravelMemory = {
  id: "memory-1",
  category: "lodging",
  content: "住宿优先靠近地铁站",
  enabled: true,
  source: "user",
  consent_at: "2026-11-14T00:00:00Z",
  created_at: "2026-11-14T00:00:00Z",
  updated_at: "2026-11-14T00:00:00Z",
};

describe("MemoryView", () => {
  beforeEach(() => {
    sessionStorage.setItem("tripmate.access-token", "token");
    setActivePinia(createPinia());
    useAuthStore();
    vi.mocked(memoryApi.list).mockResolvedValue([memory]);
    vi.mocked(memoryApi.remove).mockResolvedValue();
  });

  it("renders authorized memories and deletes only after confirmation", async () => {
    const wrapper = mount(MemoryView);
    await flushPromises();

    expect(wrapper.text()).toContain(memory.content);
    await wrapper.get('button[aria-label="删除记忆"]').trigger("click");
    expect(wrapper.text()).toContain("删除这条记忆？");
    expect(memoryApi.remove).not.toHaveBeenCalled();

    await wrapper
      .findAll("button")
      .find((button) => button.text().includes("确认删除"))!
      .trigger("click");
    await flushPromises();

    expect(memoryApi.remove).toHaveBeenCalledWith("token", "memory-1");
    expect(wrapper.text()).not.toContain(memory.content);
  });

  it("submits a memory only when consent is checked", async () => {
    vi.mocked(memoryApi.create).mockResolvedValue({
      ...memory,
      id: "memory-2",
      content: "不吃香菜",
    });
    const wrapper = mount(MemoryView);
    await flushPromises();

    await wrapper.get('input[placeholder="例如：住宿优先靠近地铁站"]').setValue("不吃香菜");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(memoryApi.create).toHaveBeenCalledWith("token", {
      category: "preference",
      content: "不吃香菜",
      consent: true,
    });
  });

  it("keeps a newly created memory when the initial list resolves later", async () => {
    let resolveList!: (value: TravelMemory[]) => void;
    vi.mocked(memoryApi.list).mockReturnValue(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );
    vi.mocked(memoryApi.create).mockResolvedValue({
      ...memory,
      id: "memory-2",
      content: "不吃香菜",
    });
    const wrapper = mount(MemoryView);

    await wrapper.get('input[placeholder="例如：住宿优先靠近地铁站"]').setValue("不吃香菜");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("不吃香菜");

    resolveList([]);
    await flushPromises();
    expect(wrapper.text()).toContain("不吃香菜");
  });
});
