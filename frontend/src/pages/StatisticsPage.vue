<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import MetricCard from "@/components/common/MetricCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import StatisticsPdfExportDialog from "@/features/statistics/StatisticsPdfExportDialog.vue";
import { useStatisticsOverview } from "@/composables/useStatisticsOverview";
import StatisticsSampleGallerySummarySection from "@/features/statistics/StatisticsSampleGallerySummarySection.vue";
import type { DetectionResult, ReviewStatus, StatisticsPdfExportMode } from "@/types/api";
import type { DailyTrendItem } from "@/types/models";
import {
  buildTrendAreaPath,
  buildTrendAxisTicks,
  buildTrendSeriesPoints,
  buildTrendSmoothPath,
  buildTrendValueTicks,
  type TrendAxisTick,
  type TrendChartPoint,
  type TrendValueTick,
} from "@/utils/trendChart";
import { formatDateTime } from "@/utils/format";

/**
 * 单条趋势线的展示状态。
 */
interface TrendSeries {
  label: string;
  color: string;
  values: number[];
  linePath: string;
  areaPath: string;
  points: TrendChartPoint[];
}

/**
 * 页面模板最终消费的横轴刻度状态。
 * 这里额外补上 `x` 坐标，避免模板层再重复计算图表布局。
 */
interface TrendAxisTickState extends TrendAxisTick {
  x: number;
}

/**
 * 页面模板消费的纵轴刻度状态。
 * 这里额外保留 `y` 坐标，避免模板层做重复映射。
 */
interface TrendValueTickState extends TrendValueTick {
  y: number;
}

/**
 * 趋势图 hover 热区。
 * 通过透明矩形覆盖每个日期区间，能让用户更容易“碰到”真实数据点。
 */
interface TrendInteractionZone {
  index: number;
  x: number;
  width: number;
}

/**
 * 趋势图悬停快照。
 * 这里集中整理当前日期下的三条序列值，模板层就不需要自己按下标拼装。
 */
interface TrendActiveSnapshotItem {
  label: string;
  color: string;
  value: number;
  point: TrendChartPoint | null;
}

/**
 * 统计页趋势图的完整渲染状态。
 */
interface TrendChartState {
  axisTicks: TrendAxisTickState[];
  valueTicks: TrendValueTickState[];
  series: TrendSeries[];
  interactionZones: TrendInteractionZone[];
  chartLeft: number;
  chartRight: number;
  chartBottom: number;
}

const QUICK_DAY_PRESETS = [7, 14, 30, 60];
const TREND_CHART_WIDTH = 660;
const TREND_CHART_HEIGHT = 320;
const TREND_CHART_PADDING = {
  top: 24,
  right: 28,
  bottom: 56,
  left: 58,
};

const {
  days,
  dateRange,
  selectedPartId,
  selectedDeviceId,
  loading,
  aiLoading,
  referenceLoading,
  pdfExporting,
  overview,
  aiAnalysis,
  error,
  aiError,
  referenceError,
  runtimeModels,
  partOptions,
  deviceOptions,
  selectedModelId,
  analysisNote,
  activeRuntimeModel,
  selectedPartLabel,
  selectedDeviceLabel,
  refresh,
  applyQuickDays,
  resetFilters,
  runAiAnalysis,
  exportPng,
  exportPdf,
} = useStatisticsOverview();

/**
 * 当前趋势图悬停的日期点。
 * `null` 表示未悬停，此时默认回退到最后一个日期点，符合“先看最新状态”的习惯。
 */
const hoveredTrendIndex = ref<number | null>(null);

/**
 * PDF 导出版本选择弹窗显隐状态。
 * 导出前先让用户明确选“视觉版”还是“轻量报表版”。
 */
const pdfExportDialogVisible = ref(false);

/**
 * 当前统计概览中的摘要数据。
 */
const summary = computed(() => overview.value?.summary ?? null);

/**
 * 缺陷分布、排行和关键发现都在页面内多处复用，这里集中展开成易读计算属性。
 */
const defectItems = computed(() => overview.value?.defectDistribution ?? []);
const partRanking = computed(() => overview.value?.partQualityRanking ?? []);
const deviceRanking = computed(() => overview.value?.deviceQualityRanking ?? []);
const keyFindings = computed(() => overview.value?.keyFindings ?? []);
const resultDistribution = computed(() => overview.value?.resultDistribution ?? []);
const reviewStatusDistribution = computed(() => overview.value?.reviewStatusDistribution ?? []);
/**
 * 统计页下半区会直接消费当前窗口内的样本图库摘要，
 * 用于展示总入口、分类入口和跳转到单条复检界面的按钮。
 */
const sampleGallery = computed(() => overview.value?.sampleGallery ?? null);

/**
 * 导出和 UI 标题中都需要展示当前筛选作用范围。
 */
const scopeDescription = computed(() => {
  if (!overview.value) {
    return "尚未生成统计窗口";
  }

  const filterParts = [
    `${overview.value.filters.startDate ?? "未限定"} 至 ${overview.value.filters.endDate ?? "未限定"}`,
    `窗口 ${overview.value.filters.days} 天`,
  ];

  if (selectedPartLabel.value) {
    filterParts.push(`零件 ${selectedPartLabel.value}`);
  }
  if (selectedDeviceLabel.value) {
    filterParts.push(`设备 ${selectedDeviceLabel.value}`);
  }

  return filterParts.join(" | ");
});

/**
 * 结果分布与审核分布使用同一套圆环图样式生成逻辑。
 */
const resultDistributionStyle = computed(() =>
  buildConicGradient(resultDistribution.value, (item) => getResultColor(item.result)),
);

const reviewDistributionStyle = computed(() =>
  buildConicGradient(reviewStatusDistribution.value, (item) =>
    getReviewStatusColor(item.reviewStatus),
  ),
);

/**
 * 自定义 SVG 趋势图的数据准备。
 */
const trendChart = computed(() => createTrendChartState(overview.value?.dailyTrend ?? []));

/**
 * 当前高亮的趋势点下标。
 * 未悬停时默认高亮最后一个时间点，方便用户打开页面先看到最新状态。
 */
const activeTrendIndex = computed<number | null>(() => {
  const totalPointCount = trendChart.value.series[0]?.points.length ?? 0;
  if (totalPointCount <= 0) {
    return null;
  }

  return hoveredTrendIndex.value ?? totalPointCount - 1;
});

/**
 * 当前趋势图顶部摘要区展示的数据快照。
 */
const activeTrendSnapshot = computed<{
  date: string;
  items: TrendActiveSnapshotItem[];
} | null>(() => {
  if (!overview.value || activeTrendIndex.value === null) {
    return null;
  }

  const currentTrendItem = overview.value.dailyTrend[activeTrendIndex.value];
  if (!currentTrendItem) {
    return null;
  }

  return {
    date: currentTrendItem.date,
    items: trendChart.value.series.map((series) => ({
      label: series.label,
      color: series.color,
      value: series.values[activeTrendIndex.value ?? 0] ?? 0,
      point: series.points[activeTrendIndex.value ?? 0] ?? null,
    })),
  };
});

/**
 * 供条形排行计算宽度时复用的最大值。
 */
const maxDefectCount = computed(() =>
  Math.max(...defectItems.value.map((item) => item.count), 1),
);
const maxPartRiskCount = computed(() =>
  Math.max(...partRanking.value.map((item) => item.badCount + item.uncertainCount), 1),
);
const maxDeviceRiskCount = computed(() =>
  Math.max(...deviceRanking.value.map((item) => item.badCount + item.uncertainCount), 1),
);

/**
 * 当前是否已经有可展示或导出的统计内容。
 */
const hasOverview = computed(() => overview.value !== null);

/**
 * 百分比统一转成 1 位小数，保证统计卡片和排行口径一致。
 */
function formatPercentValue(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

/**
 * 把最终结果枚举映射为用户可读的中文标签。
 */
function getResultLabel(result: DetectionResult): string {
  if (result === "good") {
    return "良品";
  }
  if (result === "bad") {
    return "不良";
  }
  return "待确认";
}

/**
 * 结果分布中的颜色映射。
 */
function getResultColor(result: DetectionResult): string {
  if (result === "good") {
    return "#4ad49a";
  }
  if (result === "bad") {
    return "#ff7a6d";
  }
  return "#ffcc62";
}

/**
 * 把审核状态映射为中文标签。
 */
function getReviewStatusLabel(reviewStatus: ReviewStatus): string {
  if (reviewStatus === "reviewed") {
    return "已审核";
  }
  if (reviewStatus === "ai_reserved") {
    return "AI 预留";
  }
  return "待审核";
}

/**
 * 审核状态圆环图与图例的颜色映射。
 */
function getReviewStatusColor(reviewStatus: ReviewStatus): string {
  if (reviewStatus === "reviewed") {
    return "#4ad49a";
  }
  if (reviewStatus === "ai_reserved") {
    return "#6aa7ff";
  }
  return "#ffcc62";
}

/**
 * 构造圆环图的 conic-gradient 文本。
 */
function buildConicGradient<TItem extends { count: number }>(
  items: TItem[],
  colorResolver: (item: TItem) => string,
): string {
  const totalCount = items.reduce((sum, item) => sum + item.count, 0);
  if (totalCount <= 0) {
    return "conic-gradient(rgba(149, 184, 223, 0.18) 0deg 360deg)";
  }

  let currentAngle = 0;
  const gradientParts = items.map((item) => {
    const nextAngle = currentAngle + (item.count / totalCount) * 360;
    const gradientPart = `${colorResolver(item)} ${currentAngle.toFixed(1)}deg ${nextAngle.toFixed(1)}deg`;
    currentAngle = nextAngle;
    return gradientPart;
  });

  return `conic-gradient(${gradientParts.join(", ")})`;
}

function createTrendInteractionZones(points: TrendChartPoint[]): TrendInteractionZone[] {
  if (points.length === 0) {
    return [];
  }

  return points.map((point, index) => {
    const previousPoint = points[index - 1];
    const nextPoint = points[index + 1];
    const leftBoundary = previousPoint ? (previousPoint.x + point.x) / 2 : TREND_CHART_PADDING.left;
    const rightBoundary = nextPoint
      ? (point.x + nextPoint.x) / 2
      : TREND_CHART_WIDTH - TREND_CHART_PADDING.right;

    return {
      index,
      x: leftBoundary,
      width: Math.max(rightBoundary - leftBoundary, 18),
    };
  });
}

/**
 * 把趋势数据整理成页面模板直接可用的图表状态。
 */
function createTrendChartState(items: DailyTrendItem[]): TrendChartState {
  const chartLeft = TREND_CHART_PADDING.left;
  const chartTop = TREND_CHART_PADDING.top;
  const chartRight = TREND_CHART_WIDTH - TREND_CHART_PADDING.right;
  const chartBottom = TREND_CHART_HEIGHT - TREND_CHART_PADDING.bottom;
  const chartWidth = chartRight - chartLeft;
  const chartHeight = chartBottom - chartTop;
  const seriesDefinitions = [
    {
      label: "总量",
      color: "#7fe4d0",
      values: items.map((item) => item.totalCount),
      withArea: true,
    },
    {
      label: "不良",
      color: "#ff7a6d",
      values: items.map((item) => item.badCount),
      withArea: false,
    },
    {
      label: "待确认",
      color: "#ffcc62",
      values: items.map((item) => item.uncertainCount),
      withArea: false,
    },
  ] as const;
  const rawMaxValue = Math.max(
    ...seriesDefinitions.flatMap((series) => series.values),
    1,
  );
  const valueTicks = buildTrendValueTicks(rawMaxValue).map((item) => ({
    ...item,
    y: chartTop + chartHeight - chartHeight * item.ratio,
  }));
  const chartMaxValue = valueTicks[valueTicks.length - 1]?.value ?? rawMaxValue;
  const series = seriesDefinitions.map<TrendSeries>((series) => {
    const points = buildTrendSeriesPoints(series.values, {
      x: chartLeft,
      y: chartTop,
      width: chartWidth,
      height: chartHeight,
    }, {
      maxValue: chartMaxValue,
    });

    return {
      label: series.label,
      color: series.color,
      values: series.values,
      linePath: buildTrendSmoothPath(points),
      areaPath: series.withArea ? buildTrendAreaPath(points, chartBottom) : "",
      points,
    };
  });

  return {
    axisTicks: buildTrendAxisTicks(items).map((item) => ({
      ...item,
      x: chartLeft + chartWidth * item.ratio,
    })),
    valueTicks,
    series,
    interactionZones: createTrendInteractionZones(series[0]?.points ?? []),
    chartLeft,
    chartRight,
    chartBottom,
  };
}

/**
 * 用于趋势图顶部摘要区展示日期文案。
 */
function formatTrendDate(date: string): string {
  return date;
}

/**
 * 把风险条形图的值换算成百分比宽度。
 */
function buildRiskWidth(value: number, maxValue: number): string {
  return `${Math.max((value / Math.max(maxValue, 1)) * 100, 4)}%`;
}

/**
 * 处理快捷时间窗口切换。
 */
async function handleQuickRangeChange(nextDays: number): Promise<void> {
  try {
    await applyQuickDays(nextDays);
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "统计窗口切换失败");
  }
}

/**
 * 处理 AI 批次分析请求。
 */
async function handleRunAiAnalysis(): Promise<void> {
  try {
    await runAiAnalysis();
  } catch (caughtError) {
    ElMessage.error(aiError.value || (caughtError instanceof Error ? caughtError.message : "统计 AI 分析失败"));
  }
}

/**
 * 导出 PNG 时需要把异常转换成用户可读提示。
 */
async function handleExportPng(): Promise<void> {
  try {
    await exportPng();
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "统计图片导出失败");
  }
}

/**
 * 打开 PDF 导出版本选择弹窗。
 */
function handleOpenPdfExportDialog(): void {
  pdfExportDialogVisible.value = true;
}

/**
 * 根据用户选择的导出版本触发实际 PDF 导出。
 */
function handleConfirmPdfExport(exportMode: StatisticsPdfExportMode): void {
  pdfExportDialogVisible.value = false;
  exportPdf(exportMode);
}

/**
 * 当鼠标离开趋势图时，恢复为“最后一个日期点”的默认高亮状态。
 */
function handleTrendMouseLeave(): void {
  hoveredTrendIndex.value = null;
}
</script>

<template>
  <div class="page-grid stats-page">
    <section class="stats-page__hero">
      <PageHeader
        eyebrow="Analytics"
        title="统计分析"
        description="这里不再只是表格汇总，而是围绕当前批次构建趋势曲线、风险分布、零件/设备排行、关键发现和 AI 批次分析工作台。AI 分析会直接读取当前统计窗口内的图表数据与聚合结果，不会脱离上下文泛泛回答。"
      />

      <div class="stats-page__hero-actions">
        <ElButton @click="refresh" :loading="loading">刷新概览</ElButton>
        <ElButton plain :disabled="!hasOverview" @click="handleExportPng">导出图片</ElButton>
        <ElButton
          type="primary"
          plain
          :loading="pdfExporting"
          :disabled="!hasOverview"
          @click="handleOpenPdfExportDialog"
        >
          导出 PDF
        </ElButton>
      </div>
    </section>

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      title="统计概览加载失败"
      :description="error"
    />

    <ElAlert
      v-else-if="referenceError"
      type="warning"
      show-icon
      :closable="false"
      title="部分辅助选项加载失败"
      :description="referenceError"
    />

    <section class="app-panel stats-filter-card">
      <div class="stats-filter-card__header">
        <div>
          <strong>筛选窗口</strong>
          <p class="muted-text">
            当前范围：{{ scopeDescription }}
          </p>
        </div>
        <ElTag effect="dark" round type="info">
          {{ overview ? `生成于 ${formatDateTime(overview.generatedAt)}` : "等待首次加载" }}
        </ElTag>
      </div>

      <div class="stats-filter-card__quick-range">
        <span class="muted-text">快捷窗口</span>
        <ElButton
          v-for="preset in QUICK_DAY_PRESETS"
          :key="preset"
          size="small"
          round
          :type="days === preset && dateRange.length === 0 ? 'primary' : 'default'"
          @click="handleQuickRangeChange(preset)"
        >
          近 {{ preset }} 天
        </ElButton>
      </div>

      <div class="stats-filter-card__controls">
        <ElDatePicker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          unlink-panels
          clearable
        />

        <ElSelect
          v-model="selectedPartId"
          clearable
          filterable
          :loading="referenceLoading"
          placeholder="筛选零件"
        >
          <ElOption
            v-for="item in partOptions"
            :key="item.id"
            :label="`${item.name} / ${item.partCode}`"
            :value="item.id"
          />
        </ElSelect>

        <ElSelect
          v-model="selectedDeviceId"
          clearable
          filterable
          :loading="referenceLoading"
          placeholder="筛选设备"
        >
          <ElOption
            v-for="item in deviceOptions"
            :key="item.id"
            :label="`${item.name} / ${item.deviceCode}`"
            :value="item.id"
          />
        </ElSelect>

        <div class="stats-filter-card__actions">
          <ElButton type="primary" :loading="loading" @click="refresh">应用筛选</ElButton>
          <ElButton plain @click="resetFilters">重置</ElButton>
        </div>
      </div>
    </section>

    <div v-if="summary" class="stats-page__metrics">
      <MetricCard
        label="总检测量"
        :value="String(summary.totalCount)"
        hint="当前筛选窗口内的完整记录规模"
      />
      <MetricCard
        label="当前良率"
        :value="formatPercentValue(summary.passRate)"
        hint="良品占最终生效结果的比例"
        accent="success"
      />
      <MetricCard
        label="待确认"
        :value="String(summary.uncertainCount)"
        hint="需要结合复核或补充证据进一步确认"
        accent="warning"
      />
      <MetricCard
        label="待审核"
        :value="String(summary.pendingReviewCount)"
        hint="可作为人工复核队列的优先入口"
        accent="info"
      />
    </div>

    <div v-if="overview" class="stats-page__content">
      <StatisticsSampleGallerySummarySection
        :gallery="sampleGallery"
        :filters="overview?.filters ?? null"
      />

      <div class="stats-page__chart-grid">
        <section class="app-panel stats-panel">
          <div class="stats-panel__header">
            <div>
              <strong>趋势曲线</strong>
              <p class="muted-text">观察检测总量、不良与待确认的波动，不再只看静态表格。</p>
            </div>
          </div>

          <div v-if="trendChart.axisTicks.length > 0" class="stats-trend">
            <div class="stats-trend__summary">
              <div>
                <strong>
                  {{ activeTrendSnapshot ? `${formatTrendDate(activeTrendSnapshot.date)} 的趋势快照` : "趋势快照" }}
                </strong>
                <p class="muted-text">
                  当前高亮日期下，可以直接看到总量、不良与待确认的实际数量，而不是只盯着一条线。
                </p>
              </div>

              <div v-if="activeTrendSnapshot" class="stats-trend__summary-pills">
                <span
                  v-for="item in activeTrendSnapshot.items"
                  :key="item.label"
                  class="stats-trend__summary-pill"
                >
                  <i :style="{ backgroundColor: item.color }" />
                  {{ item.label }} {{ item.value }}
                </span>
              </div>
            </div>

            <svg
              class="stats-trend__svg"
              :viewBox="`0 0 ${TREND_CHART_WIDTH} ${TREND_CHART_HEIGHT}`"
              role="img"
              aria-label="统计趋势曲线"
              @mouseleave="handleTrendMouseLeave"
            >
              <defs>
                <linearGradient id="stats-trend-area" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stop-color="#7fe4d0" stop-opacity="0.26" />
                  <stop offset="100%" stop-color="#7fe4d0" stop-opacity="0.02" />
                </linearGradient>
              </defs>

              <line
                :x1="trendChart.chartLeft"
                :x2="trendChart.chartLeft"
                :y1="TREND_CHART_PADDING.top"
                :y2="trendChart.chartBottom"
                class="stats-trend__axis"
              />
              <line
                :x1="trendChart.chartLeft"
                :x2="trendChart.chartRight"
                :y1="trendChart.chartBottom"
                :y2="trendChart.chartBottom"
                class="stats-trend__axis"
              />

              <g v-for="tick in trendChart.valueTicks" :key="`value-${tick.label}`">
                <line
                  :x1="trendChart.chartLeft"
                  :x2="trendChart.chartRight"
                  :y1="tick.y"
                  :y2="tick.y"
                  class="stats-trend__grid"
                />
                <text
                  :x="trendChart.chartLeft - 12"
                  :y="tick.y + 4"
                  text-anchor="end"
                  class="stats-trend__value-label"
                >
                  {{ tick.label }}
                </text>
              </g>

              <path
                v-if="trendChart.series[0]?.areaPath"
                :d="trendChart.series[0].areaPath"
                fill="url(#stats-trend-area)"
                stroke="none"
              />

              <line
                v-if="activeTrendSnapshot?.items[0]?.point"
                :x1="activeTrendSnapshot.items[0].point.x"
                :x2="activeTrendSnapshot.items[0].point.x"
                :y1="TREND_CHART_PADDING.top"
                :y2="trendChart.chartBottom"
                class="stats-trend__cursor-line"
              />

              <path
                v-for="series in trendChart.series"
                :key="series.label"
                :d="series.linePath"
                fill="none"
                :stroke="series.color"
                stroke-width="4"
                stroke-linecap="round"
                stroke-linejoin="round"
              />

              <g v-for="series in trendChart.series" :key="`points-${series.label}`">
                <circle
                  v-for="point in series.points"
                  :key="`${series.label}-${point.index}`"
                  :cx="point.x"
                  :cy="point.y"
                  :r="activeTrendIndex === point.index ? 5.8 : 3.2"
                  :fill="series.color"
                  :stroke="activeTrendIndex === point.index ? '#0f2136' : 'rgba(15, 33, 54, 0.58)'"
                  :stroke-width="activeTrendIndex === point.index ? 2.4 : 1.2"
                  :opacity="activeTrendIndex === point.index ? 1 : 0.78"
                />
              </g>

              <rect
                v-for="zone in trendChart.interactionZones"
                :key="`zone-${zone.index}`"
                :x="zone.x"
                :y="TREND_CHART_PADDING.top"
                :width="zone.width"
                :height="trendChart.chartBottom - TREND_CHART_PADDING.top"
                fill="transparent"
                @mouseenter="hoveredTrendIndex = zone.index"
              />

              <text
                v-for="tick in trendChart.axisTicks"
                :key="`${tick.label}-${tick.index}`"
                :x="tick.x"
                :y="TREND_CHART_HEIGHT - 14"
                text-anchor="middle"
                class="stats-trend__label"
              >
                {{ tick.label }}
              </text>
            </svg>

            <div class="stats-trend__legend">
              <span
                v-for="series in trendChart.series"
                :key="series.label"
                class="stats-trend__legend-item"
              >
                <i :style="{ backgroundColor: series.color }" />
                {{ series.label }}
              </span>
            </div>
          </div>

          <ElEmpty v-else description="当前窗口没有趋势数据" />
        </section>

        <section class="app-panel stats-panel">
          <div class="stats-panel__header">
            <div>
              <strong>结果与审核分布</strong>
              <p class="muted-text">用结构化分布快速判断当前批次是质量问题，还是审核积压在影响判断。</p>
            </div>
          </div>

          <div class="stats-distribution-grid">
            <article class="stats-distribution-card">
              <div class="stats-distribution-card__donut" :style="{ background: resultDistributionStyle }">
                <div class="stats-distribution-card__donut-center">
                  <strong>{{ summary?.totalCount ?? 0 }}</strong>
                  <span>样本总量</span>
                </div>
              </div>

              <div class="stats-distribution-card__list">
                <div
                  v-for="item in resultDistribution"
                  :key="item.result"
                  class="stats-distribution-card__item"
                >
                  <span class="stats-distribution-card__label">
                    <i :style="{ backgroundColor: getResultColor(item.result) }" />
                    {{ getResultLabel(item.result) }}
                  </span>
                  <strong>{{ item.count }}</strong>
                </div>
              </div>
            </article>

            <article class="stats-distribution-card">
              <div class="stats-distribution-card__donut" :style="{ background: reviewDistributionStyle }">
                <div class="stats-distribution-card__donut-center">
                  <strong>{{ summary?.reviewedCount ?? 0 }}</strong>
                  <span>已审核</span>
                </div>
              </div>

              <div class="stats-distribution-card__list">
                <div
                  v-for="item in reviewStatusDistribution"
                  :key="item.reviewStatus"
                  class="stats-distribution-card__item"
                >
                  <span class="stats-distribution-card__label">
                    <i :style="{ backgroundColor: getReviewStatusColor(item.reviewStatus) }" />
                    {{ getReviewStatusLabel(item.reviewStatus) }}
                  </span>
                  <strong>{{ item.count }}</strong>
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>

      <div class="stats-page__insight-grid">
        <section class="app-panel stats-panel">
          <div class="stats-panel__header">
            <div>
              <strong>缺陷分布</strong>
              <p class="muted-text">优先识别当前批次最集中的缺陷类型，而不是逐条翻表。</p>
            </div>
          </div>

          <div v-if="defectItems.length > 0" class="stats-bars">
            <article
              v-for="item in defectItems.slice(0, 6)"
              :key="item.defectType"
              class="stats-bars__row"
            >
              <div class="stats-bars__meta">
                <strong>{{ item.defectType }}</strong>
                <span>{{ item.count }}</span>
              </div>
              <div class="stats-bars__track">
                <div
                  class="stats-bars__fill stats-bars__fill--defect"
                  :style="{ width: buildRiskWidth(item.count, maxDefectCount) }"
                />
              </div>
            </article>
          </div>

          <ElEmpty v-else description="当前窗口没有缺陷分布数据" />
        </section>

        <section class="app-panel stats-panel">
          <div class="stats-panel__header">
            <div>
              <strong>关键发现</strong>
              <p class="muted-text">这些结论会直接作为统计 AI 分析的结构化上下文之一。</p>
            </div>
          </div>

          <div v-if="keyFindings.length > 0" class="stats-findings">
            <article
              v-for="(item, index) in keyFindings"
              :key="`${index}-${item}`"
              class="stats-findings__item"
            >
              <span class="stats-findings__badge">{{ index + 1 }}</span>
              <p>{{ item }}</p>
            </article>
          </div>

          <ElEmpty v-else description="当前窗口还没有可提炼的关键发现" />
        </section>
      </div>

      <div class="stats-page__ranking-grid">
        <section class="app-panel stats-panel">
          <div class="stats-panel__header">
            <div>
              <strong>零件风险排行</strong>
              <p class="muted-text">按不良与待确认规模排序，帮助定位是否由特定零件批次导致。</p>
            </div>
          </div>

          <div v-if="partRanking.length > 0" class="stats-ranking">
            <article
              v-for="item in partRanking"
              :key="item.partId"
              class="stats-ranking__row"
            >
              <div class="stats-ranking__meta">
                <div>
                  <strong>{{ item.partName }}</strong>
                  <p class="muted-text">{{ item.partCode }}</p>
                </div>
                <div class="stats-ranking__summary">
                  <span>总量 {{ item.totalCount }}</span>
                  <span>不良 {{ item.badCount }}</span>
                  <span>待确认 {{ item.uncertainCount }}</span>
                  <span>良率 {{ formatPercentValue(item.passRate) }}</span>
                </div>
              </div>
              <div class="stats-bars__track">
                <div
                  class="stats-bars__fill stats-bars__fill--risk"
                  :style="{ width: buildRiskWidth(item.badCount + item.uncertainCount, maxPartRiskCount) }"
                />
              </div>
            </article>
          </div>

          <ElEmpty v-else description="当前窗口没有零件排行数据" />
        </section>

        <section class="app-panel stats-panel">
          <div class="stats-panel__header">
            <div>
              <strong>设备风险排行</strong>
              <p class="muted-text">用于判断异常更偏向产品端，还是集中在特定设备链路。</p>
            </div>
          </div>

          <div v-if="deviceRanking.length > 0" class="stats-ranking">
            <article
              v-for="item in deviceRanking"
              :key="item.deviceId"
              class="stats-ranking__row"
            >
              <div class="stats-ranking__meta">
                <div>
                  <strong>{{ item.deviceName }}</strong>
                  <p class="muted-text">{{ item.deviceCode }}</p>
                </div>
                <div class="stats-ranking__summary">
                  <span>总量 {{ item.totalCount }}</span>
                  <span>不良 {{ item.badCount }}</span>
                  <span>待确认 {{ item.uncertainCount }}</span>
                  <span>良率 {{ formatPercentValue(item.passRate) }}</span>
                </div>
              </div>
              <div class="stats-bars__track">
                <div
                  class="stats-bars__fill stats-bars__fill--device"
                  :style="{ width: buildRiskWidth(item.badCount + item.uncertainCount, maxDeviceRiskCount) }"
                />
              </div>
            </article>
          </div>

          <ElEmpty v-else description="当前窗口没有设备排行数据" />
        </section>
      </div>

      <section class="app-panel stats-ai-panel">
        <div class="stats-panel__header">
          <div>
            <strong>AI 批次分析</strong>
            <p class="muted-text">
              AI 会直接读取当前统计窗口的摘要、趋势、缺陷分布、零件/设备排行和关键发现，再按更完整的统计审查提示词给出复盘结论。
            </p>
          </div>
          <ElTag
            v-if="activeRuntimeModel"
            effect="dark"
            round
            type="success"
          >
            {{ activeRuntimeModel.displayName }}
          </ElTag>
        </div>

        <div class="stats-ai-panel__controls">
          <ElSelect
            v-model="selectedModelId"
            clearable
            filterable
            :loading="referenceLoading"
            placeholder="选择统计分析模型"
          >
            <ElOption
              v-for="item in runtimeModels"
              :key="item.id"
              :label="`${item.displayName} / ${item.gatewayName}`"
              :value="item.id"
            />
          </ElSelect>

          <ElInput
            v-model="analysisNote"
            type="textarea"
            :rows="4"
            resize="none"
            placeholder="可补充本轮特别关注点，例如：重点分析某零件是否存在持续恶化，或判断问题更像设备侧异常还是材料批次异常。"
          />

          <div class="stats-ai-panel__actions">
            <ElButton type="primary" :loading="aiLoading" @click="handleRunAiAnalysis">
              生成 AI 分析
            </ElButton>
            <span class="muted-text">
              {{
                activeRuntimeModel
                  ? `当前模型：${activeRuntimeModel.displayName} / ${activeRuntimeModel.gatewayName}`
                  : "未选择模型时，后端只会返回预留提示。"
              }}
            </span>
          </div>
        </div>

        <ElAlert
          v-if="aiError"
          type="error"
          show-icon
          :closable="false"
          title="统计 AI 分析失败"
          :description="aiError"
        />

        <div
          v-if="aiLoading"
          class="stats-ai-panel__thinking"
          aria-label="AI 正在分析当前统计窗口"
        >
          <div class="stats-ai-panel__thinking-dots">
            <span class="stats-ai-panel__thinking-dot" />
            <span class="stats-ai-panel__thinking-dot" />
            <span class="stats-ai-panel__thinking-dot" />
          </div>
          <p class="muted-text">
            {{
              activeRuntimeModel
                ? `${activeRuntimeModel.displayName} 正在结合统计图表、排行和关键发现生成批次分析，请稍等。`
                : "AI 正在结合统计图表、排行和关键发现生成批次分析，请稍等。"
            }}
          </p>
        </div>

        <div class="stats-ai-panel__result">
          <div class="stats-ai-panel__result-meta">
            <span>状态：{{ aiAnalysis?.status ?? (aiLoading ? "streaming" : "未生成") }}</span>
            <span>模型：{{ aiAnalysis?.providerHint ?? activeRuntimeModel?.displayName ?? "未生成" }}</span>
            <span>时间：{{ aiAnalysis ? formatDateTime(aiAnalysis.generatedAt) : "未生成" }}</span>
          </div>

          <div class="stats-ai-panel__result-body">
            {{
              aiAnalysis?.answer ||
              (aiLoading
                ? "AI 已开始流式输出分析内容，请稍等首段结果返回。"
                : "当前还没有生成统计 AI 分析。你可以先确认筛选窗口，再选择模型发起分析。")
            }}
          </div>
        </div>
      </section>
    </div>

    <section v-else-if="loading" class="app-panel stats-panel">
      <ElSkeleton animated :rows="10" />
    </section>

    <StatisticsPdfExportDialog
      v-model="pdfExportDialogVisible"
      :exporting="pdfExporting"
      @submit="handleConfirmPdfExport"
    />
  </div>
</template>

<style scoped>
.stats-page {
  gap: 22px;
}

.stats-page__hero,
.stats-filter-card__header,
.stats-filter-card__quick-range,
.stats-panel__header,
.stats-ai-panel__actions,
.stats-page__hero-actions,
.stats-ranking__meta,
.stats-ranking__summary,
.stats-distribution-card__item {
  display: flex;
  gap: 14px;
}

.stats-page__hero,
.stats-filter-card__header,
.stats-panel__header,
.stats-ai-panel__actions,
.stats-ranking__meta,
.stats-distribution-card__item {
  align-items: flex-start;
  justify-content: space-between;
}

.stats-page__hero,
.stats-filter-card__controls,
.stats-page__hero-actions,
.stats-trend__legend,
.stats-distribution-grid,
.stats-page__chart-grid,
.stats-page__insight-grid,
.stats-page__ranking-grid {
  display: grid;
  gap: 18px;
}

.stats-page__hero {
  grid-template-columns: minmax(0, 1fr) auto;
}

.stats-page__hero-actions {
  align-content: start;
  justify-items: end;
}

.stats-filter-card,
.stats-panel,
.stats-ai-panel {
  padding: 24px;
}

.stats-filter-card,
.stats-panel,
.stats-ai-panel,
.stats-bars,
.stats-findings,
.stats-ranking,
.stats-ai-panel__controls,
.stats-ai-panel__result,
.stats-ai-panel__thinking {
  display: grid;
  gap: 18px;
}

.stats-filter-card__quick-range {
  align-items: center;
  flex-wrap: wrap;
}

.stats-filter-card__controls {
  grid-template-columns: minmax(280px, 1.2fr) repeat(2, minmax(220px, 0.8fr)) auto;
  align-items: center;
}

.stats-filter-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.stats-page__metrics {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stats-page__content {
  display: grid;
  gap: 20px;
}

.stats-page__chart-grid {
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.95fr);
}

.stats-page__insight-grid,
.stats-page__ranking-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.stats-panel__header p,
.stats-filter-card__header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-trend {
  display: grid;
  gap: 16px;
}

.stats-trend__summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(127, 228, 208, 0.12);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.1), transparent 34%),
    rgba(255, 255, 255, 0.02);
}

.stats-trend__summary p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-trend__summary-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.stats-trend__summary-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(10, 25, 40, 0.72);
  color: #eef5fc;
  font-weight: 600;
}

.stats-trend__svg {
  width: 100%;
  min-height: 320px;
  overflow: visible;
}

.stats-trend__axis {
  stroke: rgba(149, 184, 223, 0.24);
}

.stats-trend__grid {
  stroke: rgba(149, 184, 223, 0.14);
  stroke-dasharray: 6 6;
}

.stats-trend__cursor-line {
  stroke: rgba(127, 228, 208, 0.22);
  stroke-dasharray: 4 6;
}

.stats-trend__label {
  fill: rgba(182, 201, 220, 0.72);
  font-size: 12px;
}

.stats-trend__value-label {
  fill: rgba(143, 168, 192, 0.74);
  font-size: 12px;
}

.stats-trend__legend {
  grid-template-columns: repeat(3, minmax(0, max-content));
  align-items: center;
}

.stats-trend__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--app-text-secondary);
}

.stats-trend__legend-item i,
.stats-trend__summary-pill i,
.stats-distribution-card__label i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.stats-distribution-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.stats-distribution-card {
  display: grid;
  gap: 18px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.02);
}

.stats-distribution-card__donut {
  position: relative;
  width: 188px;
  height: 188px;
  margin: 0 auto;
  border-radius: 999px;
}

.stats-distribution-card__donut::after {
  content: "";
  position: absolute;
  inset: 22px;
  border-radius: inherit;
  background: #0f2136;
  border: 1px solid rgba(149, 184, 223, 0.12);
}

.stats-distribution-card__donut-center {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: grid;
  place-content: center;
  text-align: center;
  gap: 8px;
}

.stats-distribution-card__donut-center strong {
  font-size: 34px;
  line-height: 1;
}

.stats-distribution-card__donut-center span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.stats-distribution-card__list {
  display: grid;
  gap: 12px;
}

.stats-distribution-card__label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--app-text-secondary);
}

.stats-bars__row,
.stats-ranking__row,
.stats-findings__item {
  display: grid;
  gap: 10px;
}

.stats-bars__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stats-bars__track {
  width: 100%;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(149, 184, 223, 0.12);
}

.stats-bars__fill {
  height: 100%;
  border-radius: inherit;
}

.stats-bars__fill--defect {
  background: linear-gradient(90deg, rgba(127, 228, 208, 0.92), rgba(57, 189, 162, 0.92));
}

.stats-bars__fill--risk {
  background: linear-gradient(90deg, rgba(255, 122, 109, 0.92), rgba(255, 181, 109, 0.92));
}

.stats-bars__fill--device {
  background: linear-gradient(90deg, rgba(106, 167, 255, 0.92), rgba(127, 228, 208, 0.92));
}

.stats-findings__item {
  grid-template-columns: auto 1fr;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(149, 184, 223, 0.1);
}

.stats-findings__item p {
  margin: 0;
  line-height: 1.8;
}

.stats-findings__badge {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  background: rgba(127, 228, 208, 0.16);
  color: #7fe4d0;
  font-weight: 700;
}

.stats-ranking__summary {
  flex-wrap: wrap;
  justify-content: flex-end;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.stats-ranking__meta p {
  margin: 6px 0 0;
}

.stats-ai-panel__controls {
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.6fr);
}

.stats-ai-panel__actions {
  grid-column: 1 / -1;
  align-items: center;
  border-top: 1px solid rgba(149, 184, 223, 0.12);
  padding-top: 16px;
}

.stats-ai-panel__thinking {
  padding: 22px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(149, 184, 223, 0.12);
}

.stats-ai-panel__thinking-dots {
  display: flex;
  gap: 8px;
}

.stats-ai-panel__thinking-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: rgba(127, 228, 208, 0.92);
  animation: stats-ai-thinking 1.2s infinite ease-in-out;
}

.stats-ai-panel__thinking-dot:nth-child(2) {
  animation-delay: 0.18s;
}

.stats-ai-panel__thinking-dot:nth-child(3) {
  animation-delay: 0.36s;
}

.stats-ai-panel__result {
  padding: 22px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(149, 184, 223, 0.1);
}

.stats-ai-panel__result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.stats-ai-panel__result-body {
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--app-text);
}

@keyframes stats-ai-thinking {
  0%,
  80%,
  100% {
    transform: scale(0.72);
    opacity: 0.45;
  }

  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 1280px) {
  .stats-page__chart-grid,
  .stats-page__insight-grid,
  .stats-page__ranking-grid,
  .stats-ai-panel__controls,
  .stats-filter-card__controls {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1080px) {
  .stats-page__metrics,
  .stats-distribution-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-page__hero {
    grid-template-columns: 1fr;
  }

  .stats-trend__summary,
  .stats-page__hero-actions,
  .stats-filter-card__header,
  .stats-panel__header,
  .stats-ai-panel__actions,
  .stats-ranking__meta,
  .stats-distribution-card__item {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-trend__summary-pills {
    justify-content: flex-start;
  }

  .stats-page__metrics,
  .stats-distribution-grid {
    grid-template-columns: 1fr;
  }

  .stats-distribution-card__donut {
    width: 164px;
    height: 164px;
  }
}
</style>
