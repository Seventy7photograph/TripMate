// 文件说明：前端功能模块：types。
export interface UploadedAsset {
  id: string;
  name: string;
  mime_type: string;
  kind: "image" | "document";
  size_bytes: number;
  created_at?: string;
  expires_at?: string;
}

export interface PendingAttachment {
  key: string;
  file: File;
  previewUrl: string | null;
}
