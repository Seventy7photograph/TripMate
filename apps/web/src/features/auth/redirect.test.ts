// 文件说明：前端功能模块：redirect.test。
import { describe, expect, it } from "vitest";

import { safeAuthRedirect } from "./redirect";

describe("safeAuthRedirect", () => {
  it("allows internal paths and rejects external or protocol-relative redirects", () => {
    expect(safeAuthRedirect("/trips?include_archived=true")).toBe(
      "/trips?include_archived=true",
    );
    expect(safeAuthRedirect("https://example.com")).toBe("/");
    expect(safeAuthRedirect("//example.com")).toBe("/");
    expect(safeAuthRedirect(null)).toBe("/");
  });
});
