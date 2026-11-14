// 文件说明：前端功能模块：redirect。
export function safeAuthRedirect(value: unknown): string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/";
}
