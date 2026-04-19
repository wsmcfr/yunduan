import type { ApiErrorResponseDto } from "@/types/api";
import { getStoredAuthToken } from "@/utils/storage";

export class ApiClientError extends Error {
  code: string;
  details: Record<string, unknown> | null;
  requestId: string;
  statusCode: number;

  constructor(
    statusCode: number,
    payload: Partial<ApiErrorResponseDto> & { message?: string },
  ) {
    super(payload.message ?? "接口请求失败");
    this.name = "ApiClientError";
    this.code = payload.code ?? "unknown_error";
    this.details = payload.details ?? null;
    this.requestId = payload.request_id ?? "";
    this.statusCode = statusCode;
  }
}

/**
 * 基础请求封装。
 * 负责统一附加令牌、解析 JSON 和转换后端错误格式。
 */
export async function apiRequest<TResponse>(
  input: string,
  init: RequestInit = {},
): Promise<TResponse> {
  const headers = new Headers(init.headers ?? {});
  const hasBody = init.body !== undefined && init.body !== null;

  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const token = getStoredAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(input, {
    ...init,
    headers,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJsonResponse = contentType.includes("application/json");
  const payload = isJsonResponse ? await response.json() : null;

  if (!response.ok) {
    throw new ApiClientError(response.status, payload ?? {});
  }

  return payload as TResponse;
}
