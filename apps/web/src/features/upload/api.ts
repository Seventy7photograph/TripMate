// 文件说明：前端功能模块：api。
import { ApiError } from "../../lib/http";
import type { UploadedAsset } from "./types";

async function uploadRequest(
  token: string,
  path: string,
  init: RequestInit,
): Promise<UploadedAsset | void> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : null;
    const message =
      typeof detail === "object" &&
      detail !== null &&
      "message" in detail &&
      typeof detail.message === "string"
        ? detail.message
        : "上传失败";
    throw new ApiError(response.status, message, detail);
  }
  return payload as UploadedAsset | void;
}

export const uploadApi = {
  async upload(token: string, file: File): Promise<UploadedAsset> {
    const body = new FormData();
    body.append("file", file);
    return (await uploadRequest(token, "/api/v1/uploads", {
      method: "POST",
      body,
    })) as UploadedAsset;
  },

  remove(token: string, assetId: string): Promise<void> {
    return uploadRequest(
      token,
      `/api/v1/uploads/${encodeURIComponent(assetId)}`,
      { method: "DELETE" },
    ) as Promise<void>;
  },
};
