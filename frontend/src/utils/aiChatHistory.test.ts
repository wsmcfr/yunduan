import { describe, expect, it } from "vitest";

import { buildAiChatHistoryPayload } from "./aiChatHistory";

describe("ai chat history utilities", () => {
  it("只保留最近的非空 user / assistant 消息", () => {
    const history = buildAiChatHistoryPayload(
      [
        { role: "assistant", content: "  第一条  " },
        { role: "user", content: "第二条" },
        { role: "assistant", content: "   " },
        { role: "user", content: "第三条" },
      ],
      {
        maxMessages: 2,
        maxTotalCharacters: 200,
      },
    );

    expect(history).toEqual([
      { role: "user", content: "第二条" },
      { role: "user", content: "第三条" },
    ]);
  });

  it("会把超长单条消息压缩成前后保留的安全内容", () => {
    const longContent = `${"A".repeat(80)}${"B".repeat(80)}`;
    const history = buildAiChatHistoryPayload(
      [
        { role: "assistant", content: longContent },
      ],
      {
        maxCharactersPerMessage: 60,
        maxTotalCharacters: 60,
      },
    );

    expect(history).toHaveLength(1);
    expect(history[0].content.length).toBeLessThanOrEqual(60);
    expect(history[0].content).toContain("中间内容已省略");
    expect(history[0].content.startsWith("AAAA")).toBe(true);
    expect(history[0].content.endsWith("BBBB")).toBe(true);
  });

  it("会在总预算不足时优先保留最近几轮上下文", () => {
    const history = buildAiChatHistoryPayload(
      [
        { role: "assistant", content: "旧消息一" },
        { role: "user", content: "旧消息二" },
        { role: "assistant", content: "最新消息三" },
      ],
      {
        maxMessages: 3,
        maxTotalCharacters: 8,
      },
    );

    expect(history).toEqual([
      { role: "assistant", content: "最新消息三" },
    ]);
  });
});
