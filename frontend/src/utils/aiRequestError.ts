import { ApiClientError } from "@/services/api/client";

/**
 * 尝试从供应商原始响应里提取更稳定的错误说明。
 * 这里优先解析常见的 JSON 错误结构，解析失败时再谨慎回退到纯文本。
 */
function extractProviderMessage(responsePayload: unknown): string {
  if (typeof responsePayload !== "string") {
    return "";
  }

  const normalizedResponse = responsePayload.trim();
  if (!normalizedResponse) {
    return "";
  }

  try {
    const parsedPayload = JSON.parse(normalizedResponse) as {
      error?: { message?: unknown } | null;
      message?: unknown;
      detail?: unknown;
    };

    const messageCandidates = [
      parsedPayload.error?.message,
      parsedPayload.message,
      parsedPayload.detail,
    ];

    for (const candidate of messageCandidates) {
      if (typeof candidate === "string" && candidate.trim()) {
        return candidate.trim();
      }
    }
  } catch {
    // 供应商不一定总返回 JSON；只要不是 HTML，就允许把短文本直接展示出来。
  }

  if (normalizedResponse.startsWith("<")) {
    return "";
  }

  return normalizedResponse;
}

/**
 * 判断供应商消息是否明确指向额度、配额或月度消费上限。
 * 这一类问题本质上不是鉴权失败，必须单独提示，避免误导用户去改密钥。
 */
function isQuotaOrCreditMessage(message: string): boolean {
  const normalizedMessage = message.toLowerCase();
  return [
    "used all available credits",
    "monthly spending limit",
    "purchase more credits",
    "insufficient_quota",
    "insufficient quota",
    "credit balance",
    "billing hard limit",
    "billing quota",
  ].some((keyword) => normalizedMessage.includes(keyword));
}

/**
 * 判断供应商消息是否指向认证头、API Key 或权限校验失败。
 * 只有这类关键词命中时，前端才应该把它翻译成“鉴权失败”。
 */
function isAuthenticationMessage(message: string): boolean {
  const normalizedMessage = message.toLowerCase();
  return [
    "invalid api key",
    "incorrect api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "api key",
    "access token",
    "authorization",
    "permission denied",
  ].some((keyword) => normalizedMessage.includes(keyword));
}

/**
 * 判断供应商消息是否偏向速率限制，而不是余额耗尽。
 * 同一个 429 里，限流和额度不足属于两个完全不同的排查方向。
 */
function isRateLimitMessage(message: string): boolean {
  const normalizedMessage = message.toLowerCase();
  return [
    "rate limit",
    "too many requests",
    "requests per minute",
    "tokens per minute",
    "request rate",
  ].some((keyword) => normalizedMessage.includes(keyword));
}

/**
 * 把 AI 供应商相关错误翻译成更适合一线用户理解的提示语。
 * 这层统一供单条记录 AI 对话和统计 AI 工作台复用，避免不同页面各自误判错误类型。
 */
export function getAiProviderErrorMessage(caughtError: unknown, fallbackMessage: string): string {
  if (!(caughtError instanceof ApiClientError)) {
    return caughtError instanceof Error ? caughtError.message : fallbackMessage;
  }

  if (
    caughtError.code === "ai_provider_invalid_json" &&
    typeof caughtError.details?.response === "string"
  ) {
    const normalizedResponse = caughtError.details.response.trim();
    if (normalizedResponse.startsWith("<")) {
      return "AI 供应商返回了网页内容而不是接口 JSON，通常表示网关 URL、协议或鉴权配置不匹配。";
    }
    return "AI 供应商返回的内容不符合当前协议格式，通常表示网关 URL、模型协议或中转规则配置有误。";
  }

  if (caughtError.code === "ai_provider_http_error") {
    const providerMessage = extractProviderMessage(caughtError.details?.response);
    const upstreamStatusCode =
      typeof caughtError.details?.status_code === "number"
        ? caughtError.details.status_code
        : caughtError.statusCode;
    const retryAfter =
      typeof caughtError.details?.retry_after === "string"
        ? caughtError.details.retry_after.trim()
        : "";

    if (providerMessage && isQuotaOrCreditMessage(providerMessage)) {
      return `AI 供应商额度已用尽或达到月度上限：${providerMessage}`;
    }

    if (upstreamStatusCode === 429 || (providerMessage && isRateLimitMessage(providerMessage))) {
      const waitHint = retryAfter
        ? `建议至少等待 ${retryAfter} 秒后再重试`
        : "请稍后再重试";
      if (providerMessage) {
        return `AI 供应商已触发限流或配额限制，${waitHint}：${providerMessage}`;
      }
      return `AI 供应商已触发限流或配额限制，${waitHint}，也可以先切换到其他模型或网关。`;
    }

    if (providerMessage && isAuthenticationMessage(providerMessage)) {
      return `AI 供应商鉴权失败：${providerMessage}`;
    }

    if (providerMessage) {
      return `AI 供应商调用失败：${providerMessage}`;
    }
  }

  return caughtError.message || fallbackMessage;
}
