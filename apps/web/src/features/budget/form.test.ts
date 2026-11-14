// 文件说明：前端功能模块：form.test。
import { describe, expect, it } from "vitest";

import { parseBudgetAmount, toBudgetMinor } from "./form";

describe("budget form", () => {
  it("parses currency amounts without floating point arithmetic", () => {
    expect(parseBudgetAmount("")).toBeNull();
    expect(parseBudgetAmount("12.30")).toBe(1230);
    expect(parseBudgetAmount("0")).toBe(0);
    expect(parseBudgetAmount("12.345")).toBeUndefined();
  });

  it("maps blank amounts to zero for expense submission", () => {
    expect(toBudgetMinor("")).toBe(0);
    expect(toBudgetMinor("1.25")).toBe(125);
  });
});
