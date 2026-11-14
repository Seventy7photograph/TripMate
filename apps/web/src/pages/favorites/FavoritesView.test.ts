// 文件说明：前端页面：FavoritesView.test。
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { favoriteApi } from "../../features/share/api";
import type { Favorite } from "../../features/share/types";
import { useAuthStore } from "../../stores/auth";
import FavoritesView from "./FavoritesView.vue";

vi.mock("../../features/share/api", () => ({
  favoriteApi: {
    list: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));

const favorite: Favorite = {
  id: "favorite-1",
  kind: "place",
  target_id: "B001",
  label: "洪崖洞",
  folder: "重庆灵感",
  note: "夜景优先",
  details: { address: "重庆市渝中区" },
  created_at: "2026-11-14T00:00:00Z",
};

const tripFavorite: Favorite = {
  id: "favorite-trip-1",
  kind: "trip",
  target_id: "trip-1",
  label: "泉州古城",
  folder: "行程收藏",
  note: null,
  details: {},
  created_at: "2026-11-14T00:00:00Z",
};

describe("FavoritesView", () => {
  beforeEach(() => {
    sessionStorage.setItem("tripmate.access-token", "token");
    setActivePinia(createPinia());
    useAuthStore();
    vi.mocked(favoriteApi.list).mockResolvedValue([favorite]);
    vi.mocked(favoriteApi.update).mockResolvedValue({
      ...favorite,
      folder: "夜景收藏",
      note: "下次带相机",
    });
    vi.mocked(favoriteApi.remove).mockResolvedValue();
  });

  it("lists and filters favorite folders and notes", async () => {
    const wrapper = mount(FavoritesView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("洪崖洞");
    expect(wrapper.text()).toContain("重庆灵感");
    expect(wrapper.text()).toContain("夜景优先");
    await wrapper.get("select").setValue("重庆灵感");
    expect(wrapper.findAll(".favorite-row")).toHaveLength(1);
  });

  it("shows place and trip favorites together with distinct labels", async () => {
    vi.mocked(favoriteApi.list).mockResolvedValue([
      { ...favorite, folder: "地点收藏" },
      tripFavorite,
    ]);
    const wrapper = mount(FavoritesView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toContain(
      "全部收藏",
    );
    expect(wrapper.text()).toContain("地点收藏");
    expect(wrapper.text()).toContain("行程收藏");
    expect(wrapper.findAll(".favorite-row")).toHaveLength(2);
  });

  it("moves a favorite to another folder and saves a note", async () => {
    const wrapper = mount(FavoritesView, {
      global: {
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    await wrapper.get('button[aria-label="编辑收藏 洪崖洞"]').trigger("click");
    const inputs = wrapper.findAll(".favorite-edit-dialog input");
    await inputs[0]!.setValue("夜景收藏");
    await wrapper.get(".favorite-edit-dialog textarea").setValue("下次带相机");
    await wrapper
      .findAll(".favorite-edit-dialog button")
      .find((button) => button.text() === "保存")!
      .trigger("click");
    await flushPromises();

    expect(favoriteApi.update).toHaveBeenCalledWith("token", "favorite-1", {
      folder: "夜景收藏",
      note: "下次带相机",
    });
    expect(wrapper.text()).toContain("夜景收藏");
  });
});
