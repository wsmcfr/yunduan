import { describe, expect, it } from "vitest";

import { ApiClientError } from "@/services/api/client";

import { getAiProviderErrorMessage } from "./aiRequestError";

describe("ai request error utilities", () => {
  it("会把额度耗尽类消息翻译成月度上限提示，而不是鉴权失败", () => {
    const error = new ApiClientError(502, {
      code: "ai_provider_http_error",
      message: "AI 供应商调用失败，HTTP 429。",
      details: {
        status_code: 429,
        response: JSON.stringify({
          error: {
            message:
              "Your team demo-team has either used all available credits or reached its monthly spending limit.",
          },
        }),
      },
    });

    expect(getAiProviderErrorMessage(error, "统计 AI 分析失败")).toContain("额度已用尽或达到月度上限");
  });

  it("会优先把真实认证错误翻译成鉴权失败", () => {
    const error = new ApiClientError(502, {
      code: "ai_provider_http_error",
      message: "AI 供应商调用失败，HTTP 401。",
      details: {
        status_code: 401,
        response: JSON.stringify({
          error: {
            message: "Invalid API key provided.",
          },
        }),
      },
    });

    expect(getAiProviderErrorMessage(error, "AI 对话调用失败")).toBe(
      "AI 供应商鉴权失败：Invalid API key provided.",
    );
  });

  it("会把纯限流类消息翻译成稍后重试提示", () => {
    const error = new ApiClientError(502, {
      code: "ai_provider_http_error",
      message: "AI 供应商调用失败，HTTP 429。",
      details: {
        status_code: 429,
        retry_after: "30",
        response: JSON.stringify({
          error: {
            message: "Rate limit exceeded for requests per minute.",
          },
        }),
      },
    });

    expect(getAiProviderErrorMessage(error, "AI 对话调用失败")).toBe(
      "AI 供应商已触发限流或配额限制，建议至少等待 30 秒后再重试：Rate limit exceeded for requests per minute.",
    );
  });
});
