// 文件说明：管理后台模块：App.test。
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { beforeEach, describe, expect, it } from "vitest";

import App from "./App.vue";

describe("Admin App", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("renders admin login without an existing session", async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
      },
    });
    await flushPromises();

    expect(wrapper.get("h1").text()).toBe("管理后台");
    expect(wrapper.get("form").text()).toContain("管理员登录");
    expect(wrapper.get('input[type="email"]')).toBeTruthy();
  });
});

