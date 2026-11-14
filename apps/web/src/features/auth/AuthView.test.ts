// 文件说明：前端功能模块：AuthView.test。
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authApi, ApiError } from "./api";
import AuthView from "./AuthView.vue";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    authApi: {
      login: vi.fn(),
      register: vi.fn(),
    },
  };
});

vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" },
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}));

describe("AuthView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("clears server errors and field errors when switching mode", async () => {
    vi.mocked(authApi.login).mockRejectedValue(
      new ApiError(401, "Invalid email or password"),
    );
    const wrapper = mount(AuthView, {
      props: { mode: "login" },
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });

    await wrapper.get('input[name="email"]').setValue("user@example.com");
    await wrapper.get('input[name="password"]').setValue("wrong-password");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("邮箱或密码不正确");

    await wrapper.setProps({ mode: "register" });
    await flushPromises();
    expect(wrapper.text()).not.toContain("邮箱或密码不正确");
    expect(wrapper.find(".field-error").exists()).toBe(false);
  });

  it("shows field-level validation instead of one generic error", async () => {
    const wrapper = mount(AuthView, {
      props: { mode: "register" },
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });

    await wrapper.get('input[name="email"]').setValue("not-an-email");
    await wrapper.get('input[name="password"]').setValue("short");
    await wrapper.get('input[name="confirm_password"]').setValue("different");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("请输入有效邮箱");
    expect(wrapper.text()).toContain("密码至少 12 位");
    expect(wrapper.text()).toContain("两次输入的密码不一致");
    expect(authApi.register).not.toHaveBeenCalled();
  });

  it("uses the departure button only on the login surface", async () => {
    const wrapper = mount(AuthView, {
      props: { mode: "login" },
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });

    const loginButton = wrapper.get("button.departure-button");
    expect(loginButton.text()).toBe("出发");
    expect(loginButton.attributes("aria-label")).toBe("出发");

    await wrapper.setProps({ mode: "register" });
    expect(wrapper.find("button.departure-button").exists()).toBe(false);
    expect(wrapper.text()).toContain("创建账号");
    expect(wrapper.find("button.leaf-action").exists()).toBe(true);
  });

  it("uses the outlined reference button without an inner fill", () => {
    const wrapper = mount(AuthView, {
      props: { mode: "login" },
      global: {
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });

    expect(wrapper.find("button.departure-button .button__fill").exists()).toBe(false);
    expect(wrapper.findAll(".button__line--left")).toHaveLength(1);
    expect(wrapper.findAll(".button__line--right")).toHaveLength(1);
    expect(
      wrapper.findAll(".button__char").map((item) => item.text()),
    ).toEqual(["出", "发"]);
  });
});
