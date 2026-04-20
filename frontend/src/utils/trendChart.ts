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

/**
 * 趋势图中单个数据点的几何信息。
 * 这里把原始值也保留下来，方便页面 hover、提示框和导出文案直接复用。
 */
export interface TrendChartPoint {
  index: number;
  value: number;
  x: number;
  y: number;
}

/**
 * 趋势图纵轴刻度描述。
 * `ratio` 表示当前刻度相对于纵轴最大值的位置比例，方便不同尺寸图表复用同一组刻度。
 */
export interface TrendValueTick {
  value: number;
  label: string;
  ratio: number;
}

/**
 * 绘制趋势图时的图表内边距区域。
 * 页面图、PNG 导出图都会把原始值映射到这个矩形区域中。
 */
export interface TrendChartRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

const DEFAULT_TREND_MAX_TICK_COUNT = 7;
const DEFAULT_TREND_TARGET_Y_TICK_COUNT = 4;

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

/**
 * 把纵轴原始最大值归一化成“人眼友好”的上界。
 * 例如 13 会被抬到 15，83 会被抬到 100，避免纵轴刻度出现难读的碎值。
 */
function resolveTrendNiceMaxValue(maxValue: number, targetTickCount: number): number {
  if (maxValue <= 0) {
    return 1;
  }

  const roughStep = maxValue / Math.max(targetTickCount - 1, 1);
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const normalizedStep = roughStep / magnitude;
  const niceStep =
    normalizedStep <= 1
      ? 1
      : normalizedStep <= 2
        ? 2
        : normalizedStep <= 5
          ? 5
          : 10;

  return Math.ceil(maxValue / (niceStep * magnitude)) * niceStep * magnitude;
}

/**
 * 把纵轴刻度格式化成尽量简洁的文本。
 * 计数型趋势以整数优先，确实存在小数时只保留 1 位。
 */
function formatTrendValueLabel(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/**
 * 生成趋势图纵轴刻度。
 * 这里返回的是通用比例描述，而不是固定像素坐标，便于页面图和导出图共享。
 */
export function buildTrendValueTicks(
  maxValue: number,
  options?: {
    targetTickCount?: number;
  },
): TrendValueTick[] {
  const targetTickCount = Math.max(
    Math.floor(options?.targetTickCount ?? DEFAULT_TREND_TARGET_Y_TICK_COUNT),
    2,
  );
  const niceMaxValue = resolveTrendNiceMaxValue(maxValue, targetTickCount);
  const step = niceMaxValue / Math.max(targetTickCount - 1, 1);
  const ticks: TrendValueTick[] = [];

  for (let index = 0; index < targetTickCount; index += 1) {
    const value = step * index;
    ticks.push({
      value,
      label: formatTrendValueLabel(value),
      ratio: niceMaxValue === 0 ? 0 : value / niceMaxValue,
    });
  }

  return ticks;
}

/**
 * 把一组趋势值映射为图表内的像素点。
 * 可以通过 `maxValue` 让多条曲线共享同一根纵轴，而不是各自单独缩放。
 */
export function buildTrendSeriesPoints(
  values: number[],
  chartRect: TrendChartRect,
  options?: {
    maxValue?: number;
  },
): TrendChartPoint[] {
  const safeValues = values.length > 0 ? values : [0];
  const resolvedMaxValue = Math.max(options?.maxValue ?? Math.max(...safeValues, 1), 1);

  return safeValues.map((value, index) => ({
    index,
    value,
    x: chartRect.x + chartRect.width * resolveTrendPointRatio(index, safeValues.length),
    y: chartRect.y + chartRect.height - chartRect.height * (value / resolvedMaxValue),
  }));
}

/**
 * 把折线点序列转换成平滑曲线路径。
 * 使用 Catmull-Rom 到 Bezier 的常见换算，既比 polyline 更自然，也不会过度夸张拐点。
 */
export function buildTrendSmoothPath(
  points: Pick<TrendChartPoint, "x" | "y">[],
  options?: {
    tension?: number;
  },
): string {
  if (points.length === 0) {
    return "";
  }

  if (points.length === 1) {
    return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  }

  const tension = options?.tension ?? 1;
  const pathParts = [`M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`];

  for (let index = 0; index < points.length - 1; index += 1) {
    const previousPoint = points[index - 1] ?? points[index];
    const currentPoint = points[index];
    const nextPoint = points[index + 1];
    const afterNextPoint = points[index + 2] ?? nextPoint;

    const controlPoint1X =
      currentPoint.x + ((nextPoint.x - previousPoint.x) / 6) * tension;
    const controlPoint1Y =
      currentPoint.y + ((nextPoint.y - previousPoint.y) / 6) * tension;
    const controlPoint2X =
      nextPoint.x - ((afterNextPoint.x - currentPoint.x) / 6) * tension;
    const controlPoint2Y =
      nextPoint.y - ((afterNextPoint.y - currentPoint.y) / 6) * tension;

    pathParts.push(
      [
        "C",
        controlPoint1X.toFixed(1),
        controlPoint1Y.toFixed(1),
        controlPoint2X.toFixed(1),
        controlPoint2Y.toFixed(1),
        nextPoint.x.toFixed(1),
        nextPoint.y.toFixed(1),
      ].join(" "),
    );
  }

  return pathParts.join(" ");
}

/**
 * 为趋势曲线生成闭合的面积路径。
 * 页面上可用于主曲线底部的渐变填充，让波动范围更直观。
 */
export function buildTrendAreaPath(
  points: Pick<TrendChartPoint, "x" | "y">[],
  baselineY: number,
  options?: {
    tension?: number;
  },
): string {
  if (points.length === 0) {
    return "";
  }

  const smoothLinePath = buildTrendSmoothPath(points, options);
  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];

  return `${smoothLinePath} L ${lastPoint.x.toFixed(1)} ${baselineY.toFixed(1)} L ${firstPoint.x.toFixed(1)} ${baselineY.toFixed(1)} Z`;
}
