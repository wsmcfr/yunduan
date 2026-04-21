import type { ApiErrorResponseDto } from "@/types/api";

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
 * 把后端错误响应归一化成前端可展示的消息结构。
 * FastAPI 默认的 422 校验错误只有 `detail`，没有 `message`，这里统一补成人能看懂的提示。
 */
function normalizeApiErrorPayload(
  payload: unknown,
): Partial<ApiErrorResponseDto> & { message?: string } {
  if (typeof payload !== "object" || payload === null) {
    return {};
  }

  const normalizedPayload = payload as Partial<ApiErrorResponseDto> & {
    message?: string;
    detail?: unknown;
  };

  if (normalizedPayload.message) {
    return normalizedPayload;
  }

  if (Array.isArray(normalizedPayload.detail) && normalizedPayload.detail.length > 0) {
    const firstDetail = normalizedPayload.detail[0] as {
      msg?: string;
      loc?: unknown[];
    };
    const fieldPath = Array.isArray(firstDetail?.loc) ? firstDetail.loc.join(".") : "";
    return {
      ...normalizedPayload,
      message: fieldPath
        ? `请求参数无效：${fieldPath}，${firstDetail?.msg ?? "请检查输入。"}`
        : `请求参数无效：${firstDetail?.msg ?? "请检查输入。"}`,
    };
  }

  if (typeof normalizedPayload.detail === "string" && normalizedPayload.detail.trim()) {
    return {
      ...normalizedPayload,
      message: normalizedPayload.detail.trim(),
    };
  }

  return normalizedPayload;
}

/**
 * 统一构造请求头和请求参数。
 * 当前正式认证使用服务端 HttpOnly Cookie，因此这里不再从前端注入 Bearer Token。
 */
function buildRequestInit(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers ?? {});
  const hasBody = init.body !== undefined && init.body !== null;

  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return {
    ...init,
    headers,
    credentials: init.credentials ?? "include",
  };
}

/**
 * 把失败响应统一转换成前端可识别的异常对象。
 */
async function throwApiError(response: Response): Promise<never> {
  const contentType = response.headers.get("content-type") ?? "";
  const isJsonResponse = contentType.includes("application/json");
  const payload = isJsonResponse
    ? ((await response.json()) as Partial<ApiErrorResponseDto> & { message?: string })
    : {
        message: (await response.text()) || "接口请求失败",
      };

  throw new ApiClientError(response.status, normalizeApiErrorPayload(payload));
}

/**
 * 基础请求封装。
 * 负责统一附带 Cookie、解析 JSON 和转换后端错误格式。
 */
export async function apiRequest<TResponse>(
  input: string,
  init: RequestInit = {},
): Promise<TResponse> {
  const response = await fetch(input, buildRequestInit(init));

  const contentType = response.headers.get("content-type") ?? "";
  const isJsonResponse = contentType.includes("application/json");
  const payload = isJsonResponse ? await response.json() : null;

  if (!response.ok) {
    throw new ApiClientError(response.status, normalizeApiErrorPayload(payload ?? {}));
  }

  return payload as TResponse;
}

export interface SseEventMessage {
  event: string;
  data: unknown;
}

/**
 * 解析单个 SSE 文本块。
 * 后端固定发送 `event + JSON data`，这里统一还原成结构化事件对象。
 */
function parseSseBlock(block: string): SseEventMessage | null {
  const normalizedBlock = block.trim();
  if (!normalizedBlock) {
    return null;
  }

  let eventName = "message";
  const dataLines: string[] = [];

  for (const rawLine of normalizedBlock.split("\n")) {
    if (!rawLine || rawLine.startsWith(":")) {
      continue;
    }
    if (rawLine.startsWith("event:")) {
      eventName = rawLine.slice(6).trim() || "message";
      continue;
    }
    if (rawLine.startsWith("data:")) {
      dataLines.push(rawLine.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  const rawData = dataLines.join("\n");
  try {
    return {
      event: eventName,
      data: JSON.parse(rawData),
    };
  } catch {
    return {
      event: eventName,
      data: rawData,
    };
  }
}

/**
 * 把流式错误事件转换成统一的 API 异常。
 */
function createStreamError(data: unknown): ApiClientError {
  if (typeof data === "object" && data !== null) {
    const payload = data as {
      status_code?: number;
      code?: string;
      message?: string;
      details?: Record<string, unknown> | null;
      request_id?: string;
    };
    return new ApiClientError(payload.status_code ?? 500, {
      code: payload.code,
      message: payload.message,
      details: payload.details ?? null,
      request_id: payload.request_id,
    });
  }

  return new ApiClientError(500, {
    code: "stream_error",
    message: typeof data === "string" ? data : "流式接口返回了未知错误。",
  });
}

/**
 * 以 `POST + SSE` 的方式读取流式接口。
 * 这里不使用 `EventSource`，因为当前 AI 分析接口都需要带 JSON 请求体。
 */
export async function streamSseRequest(
  input: string,
  init: RequestInit & {
    onEvent: (event: SseEventMessage) => void | Promise<void>;
  },
): Promise<void> {
  const response = await fetch(input, buildRequestInit(init));

  if (!response.ok) {
    await throwApiError(response);
  }

  if (!response.body) {
    throw new ApiClientError(500, {
      code: "stream_body_missing",
      message: "流式响应体不可用。",
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    buffer = buffer.replace(/\r/g, "");

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex >= 0) {
      const block = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const parsedEvent = parseSseBlock(block);

      if (parsedEvent) {
        if (parsedEvent.event === "error") {
          throw createStreamError(parsedEvent.data);
        }
        await init.onEvent(parsedEvent);
      }

      separatorIndex = buffer.indexOf("\n\n");
    }

    if (done) {
      const tailEvent = parseSseBlock(buffer);
      if (tailEvent) {
        if (tailEvent.event === "error") {
          throw createStreamError(tailEvent.data);
        }
        await init.onEvent(tailEvent);
      }
      break;
    }
  }
}
