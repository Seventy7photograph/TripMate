// 文件说明：前端功能模块：BriefForm.test。
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BriefForm from "./BriefForm.vue";

describe("BriefForm", () => {
  it("keeps parsed values and emits a corrected complete brief", async () => {
    const wrapper = mount(BriefForm, {
      props: {
        initialValue: {
          destination: "重庆",
          origin: "上海",
          start_date: "2026-12-01",
          end_date: "2026-12-03",
          party_size: 2,
          budget_minor: null,
          currency: "CNY",
          interests: ["美食"],
          pace: "relaxed",
        },
        missingFields: ["budget_minor"],
      },
    });

    expect(
      (wrapper.find('input[name="destination"]').element as HTMLInputElement).value,
    ).toBe("重庆");
    expect(
      (wrapper.find('input[name="start_date"]').element as HTMLInputElement).value,
    ).toBe("2026-12-01");

    await wrapper.find('input[name="budget"]').setValue("5000");
    await wrapper.find("form").trigger("submit");

    const emitted = wrapper.emitted("submit");
    expect(emitted).toHaveLength(1);
    expect(emitted?.[0]?.[0]).toMatchObject({
      destination: "重庆",
      origin: "上海",
      start_date: "2026-12-01",
      end_date: "2026-12-03",
      party_size: 2,
      budget_minor: 500_000,
      currency: "CNY",
      interests: ["美食"],
      pace: "relaxed",
    });
  });
});
