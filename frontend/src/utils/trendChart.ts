import type { DailyTrendItem } from "@/types/models";

/**
 * 单个横轴刻度的描述。
 * `index` 用来回指原始趋势数组位置，`ratio` 用来在不同尺寸的图表里复用同一套横轴布局。
 */
export interface TrendAxisTick {
  index: number;
  label: string;
  ratio: number;
}

const DEFAULT_TREND_MAX_TICK_COUNT = 7;

/**
 * 统一截取后端返回的日期部分，避免未来接口携带时间字段时破坏前端标签格式。
 */
function normalizeTrendDate(date: string): string {
  return date.slice(0, 10);
}

/**
 * 根据时间窗口大小自适应横轴标签格式。
 * 窗口越长，标签越需要收紧，否则即使做了抽稀也可能因为文本过长再次拥挤。
 */
function formatTrendAxisLabel(date: string, totalCount: number): string {
  const normalizedDate = normalizeTrendDate(date);
  if (normalizedDate.length < 10) {
    return date;
  }

  if (totalCount > 180) {
    return normalizedDate.slice(0, 7);
  }

  return normalizedDate.slice(5);
}

/**
 * 统一计算趋势图点位在横轴上的比例位置。
 * 单点数据居中展示，多点数据则按首尾铺满，保证页面图和导出图口径一致。
 */
export function resolveTrendPointRatio(index: number, totalCount: number): number {
  if (totalCount <= 1) {
    return 0.5;
  }

  return index / (totalCount - 1);
}

/**
 * 根据趋势数据长度生成需要展示的横轴刻度。
 * 会保留首尾日期，并把中间刻度抽稀到可读范围内，避免时间窗口扩大后标签全部重叠。
 */
export function buildTrendAxisTicks(
  items: Pick<DailyTrendItem, "date">[],
  options?: {
    maxTickCount?: number;
  },
): TrendAxisTick[] {
  const totalCount = items.length;
  if (totalCount === 0) {
    return [];
  }

  const maxTickCount = Math.max(
    Math.floor(options?.maxTickCount ?? DEFAULT_TREND_MAX_TICK_COUNT),
    2,
  );

  const tickIndices =
    totalCount <= maxTickCount
      ? items.map((_, index) => index)
      : (() => {
          const nextIndices: number[] = [];
          const step = Math.ceil((totalCount - 1) / (maxTickCount - 1));

          for (let index = 0; index < totalCount; index += step) {
            nextIndices.push(index);
          }

          if (nextIndices[nextIndices.length - 1] !== totalCount - 1) {
            nextIndices.push(totalCount - 1);
          }

          return nextIndices;
        })();

  return Array.from(new Set(tickIndices)).map((index) => ({
    index,
    label: formatTrendAxisLabel(items[index]?.date ?? "", totalCount),
    ratio: resolveTrendPointRatio(index, totalCount),
  }));
}
