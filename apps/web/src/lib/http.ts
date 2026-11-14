// 文件说明：Web 前端模块：http。
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, { ...options, headers });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : null;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" &&
            detail !== null &&
            "message" in detail &&
            typeof detail.message === "string"
          ? detail.message
          : "Request failed";
    throw new ApiError(response.status, message, detail);
  }

  return payload as T;
}

export interface VersionConflictDetails {
  code: "version_conflict";
  message: string;
  current_version: number;
}

export function isVersionConflict(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    error.status === 409 &&
    typeof error.details === "object" &&
    error.details !== null &&
    "code" in error.details &&
    error.details.code === "version_conflict" &&
    "current_version" in error.details &&
    typeof error.details.current_version === "number"
  );
}

export function conflictDetails(error: ApiError): VersionConflictDetails {
  return error.details as VersionConflictDetails;
}
