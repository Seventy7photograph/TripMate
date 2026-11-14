// 文件说明：Web 前端测试：LeafActionButton。
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import LeafActionButton from "./LeafActionButton.vue";

describe("LeafActionButton", () => {
  it("renders a button with three animated leaf icons", () => {
    const wrapper = mount(LeafActionButton, {
      props: { label: "新建旅行" },
    });

    expect(wrapper.get("button").text()).toContain("新建旅行");
    expect(wrapper.findAll(".leaf-action__icon")).toHaveLength(3);
  });

  it("renders as a router link when a target is provided", () => {
    const wrapper = mount(LeafActionButton, {
      props: { label: "地图与路线", to: "/trips/trip-1/map" },
      global: {
        stubs: {
          RouterLink: {
            props: ["to"],
            template: "<a :data-to='to'><slot /></a>",
          },
        },
      },
    });

    expect(wrapper.get("a").attributes("data-to")).toBe("/trips/trip-1/map");
  });
});
