import { describe, expect, it } from "vitest";

import { buildTrendAxisTicks, resolveTrendPointRatio } from "./trendChart";

/**
 * 构造连续日期趋势数据，便于验证不同时间窗口下的横轴抽稀行为。
 */
function buildTrendItems(count: number, startDate = "2026-01-01"): Array<{ date: string }> {
  const start = new Date(`${startDate}T00:00:00Z`);

  return Array.from({ length: count }, (_, index) => {
    const nextDate = new Date(start);
    nextDate.setUTCDate(start.getUTCDate() + index);

    return {
      date: nextDate.toISOString().slice(0, 10),
    };
  });
}

describe("trend chart utilities", () => {
  it("单点趋势会放在横轴中间，多点趋势按首尾铺满", () => {
    expect(resolveTrendPointRatio(0, 1)).toBe(0.5);
    expect(resolveTrendPointRatio(0, 5)).toBe(0);
    expect(resolveTrendPointRatio(4, 5)).toBe(1);
  });

  it("短时间窗口保留全部日期刻度", () => {
    const axisTicks = buildTrendAxisTicks(buildTrendItems(7));

    expect(axisTicks).toHaveLength(7);
    expect(axisTicks.map((item) => item.label)).toEqual([
      "01-01",
      "01-02",
      "01-03",
      "01-04",
      "01-05",
      "01-06",
      "01-07",
    ]);
  });

  it("长时间窗口会自动抽稀，并保留首尾刻度", () => {
    const axisTicks = buildTrendAxisTicks(buildTrendItems(60));

    expect(axisTicks).toHaveLength(7);
    expect(axisTicks.map((item) => item.index)).toEqual([0, 10, 20, 30, 40, 50, 59]);
    expect(axisTicks[0]?.label).toBe("01-01");
    expect(axisTicks[axisTicks.length - 1]?.label).toBe("03-01");
  });

  it("超长时间窗口会自动收紧标签格式", () => {
    const axisTicks = buildTrendAxisTicks(buildTrendItems(210));

    expect(axisTicks.every((item) => /^\d{4}-\d{2}$/.test(item.label))).toBe(true);
  });
});
