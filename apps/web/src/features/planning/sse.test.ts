// 文件说明：前端功能模块：sse.test。
import { describe, expect, it } from "vitest";

import { parseSseChunks } from "./sse";

describe("SSE parser", () => {
  it("parses named events and keeps partial chunks", () => {
    const parsed = parseSseChunks([
      'event: stage\ndata: {"sequence":1,"type":"stage"}\n\n',
      'event: complete\ndata: {"sequence":2,"type":"complete","status":"completed"}',
      "\n\n",
    ]);

    expect(parsed.map((event) => event.event)).toEqual(["stage", "complete"]);
    expect(parsed[1]?.data.status).toBe("completed");
  });
});
