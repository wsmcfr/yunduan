import { describe, expect, it } from "vitest";

import {
  formatDateTimeInputValue,
  normalizeOptionalDateTime,
} from "./form";

/**
 * 生成本地日期时间输入字符串。
 * 测试里复用这个方法，确保断言逻辑和生产代码面对的是同一种本地时间语义。
 */
function buildLocalDateTimeInputValue(date: Date): string {
  const pad = (input: number) => String(input).padStart(2, "0");

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

describe("form datetime utilities", () => {
  it("将本地 datetime 输入值转换成带时区的 ISO 字符串", () => {
    /**
     * 这个用例保护跨层契约：
     * 前端表单提交给后端前，必须把本地时间补全成明确时区的 ISO 时间。
     */
    const normalizedValue = normalizeOptionalDateTime("2026-04-20T10:00:00");
    const expectedValue = new Date(2026, 3, 20, 10, 0, 0).toISOString();

    expect(normalizedValue).toBe(expectedValue);
  });

  it("保留已经带时区的 ISO 输入，只做标准化输出", () => {
    /**
     * 这个用例保护已经显式携带时区的输入，避免二次转换后丢失原始时刻。
     */
    const normalizedValue = normalizeOptionalDateTime("2026-04-20T02:00:00.000Z");

    expect(normalizedValue).toBe("2026-04-20T02:00:00.000Z");
  });

  it("将后端 ISO 时间还原成适合日期时间组件回填的本地字符串", () => {
    /**
     * 这个用例确保详情回填和编辑态使用的是本地时间展示，
     * 不会直接把 UTC 字符串原样塞给日期组件。
     */
    const sourceDate = new Date(2026, 3, 20, 10, 0, 0);
    const formattedValue = formatDateTimeInputValue(sourceDate.toISOString());

    expect(formattedValue).toBe(buildLocalDateTimeInputValue(sourceDate));
  });
});
