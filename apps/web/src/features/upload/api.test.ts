// 文件说明：前端功能模块：api.test。
import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadApi } from "./api";

describe("upload API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uploads a file with bearer auth and no manual content type", async () => {
    const asset = {
      id: "asset-1",
      name: "trip.png",
      mime_type: "image/png",
      kind: "image",
      size_bytes: 3,
      created_at: "2026-11-14T00:00:00Z",
      expires_at: "2026-11-15T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(asset), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File([new Uint8Array([1, 2, 3])], "trip.png", {
      type: "image/png",
    });

    await expect(uploadApi.upload("token", file)).resolves.toMatchObject({
      id: "asset-1",
    });

    const options = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBe(file);
    expect(options.method).toBe("POST");
    expect(options.headers).toEqual({ Authorization: "Bearer token" });
  });
});
