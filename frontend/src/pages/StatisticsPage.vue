<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import MetricCard from "@/components/common/MetricCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useAiAutoScroll } from "@/composables/useAiAutoScroll";
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

/**
 * 统计页分页工作区。
 * 这里把内容明确拆成“总览 / 风险 / 图库 / AI”四页，避免继续往下拉很久才能看到目标区域。
 */
type StatisticsWorkspacePage = "overview" | "ranking" | "gallery" | "ai";

/**
 * 统计页分页导航配置。
 * 页面导航本身就承担“第几页、这一页看什么”的提示，不再让 AI 区藏在长页面底部。
 */
const STATISTICS_WORKSPACE_PAGE_OPTIONS: Array<{
  name: StatisticsWorkspacePage;
  title: string;
  description: string;
}> = [
  {
    name: "overview",
    title: "趋势总览",
    description: "看趋势曲线、分布结构和关键发现。",
  },
  {
    name: "ranking",
    title: "风险排行",
    description: "看零件和设备风险是否集中。",
  },
  {
    name: "gallery",
    title: "样本图库",
    description: "看图片总入口，再进入独立图库复检。",
  },
  {
    name: "ai",
    title: "AI 工作台",
    description: "围绕当前统计窗口继续提问和追问。",
  },
];

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
  aiQuestion,
  visibleAiMessages,
  aiSuggestedQuestions,
  error,
  aiError,
  referenceError,
  runtimeModels,
  partOptions,
  deviceOptions,
  selectedModelId,
  analysisNote,
  chatSending,
  streamingAssistantMessageId,
  activeRuntimeModel,
  canUseAiAnalysis,
  isAiStreaming,
  selectedPartLabel,
  selectedDeviceLabel,
  refresh,
  applyQuickDays,
  resetFilters,
  runAiAnalysis,
  useSuggestedQuestion,
  submitAiQuestion,
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
const activeWorkspacePage = ref<StatisticsWorkspacePage>("overview");

/**
 * 统计页 AI 多轮消息区的自动跟随滚动控制。
 * 只要用户还停留在底部，就自动跟随最新流式输出；用户上滑查看旧消息后，暂停自动跟随。
 */
const {
  scrollbarRef: aiMessagesScrollbarRef,
  handleScroll: handleAiMessagesScroll,
} = useAiAutoScroll({
  messages: visibleAiMessages,
});

/**
 * 首轮批次分析正文区的滚动容器。
 * 因为正文区现在是独立可滚动区域，所以需要单独维护“是否跟随到底部”。
 */
const aiAnalysisBodyRef = ref<HTMLElement | null>(null);

/**
 * 当用户仍停留在正文区底部时，流式内容继续自动跟随；
 * 如果用户手动上滑查看旧内容，则暂停自动跟随，避免抢滚动位置。
 */
const shouldAutoScrollAiAnalysis = ref(true);

/**
 * 统计 AI 分析正文区是否应该占位显示。
 * 一旦点击“生成 AI 分析”，就先把正文卡片渲染出来，避免首个流式字符到达时
 * 才突然插入整块 DOM，把下方“多轮追问”整体往下顶出一次跳变。
 */
const shouldShowAiAnalysisBlock = computed(() => aiLoading.value || Boolean(aiAnalysis.value));

/**
 * 统计 AI 正文区在不同阶段展示的文本。
 * 有稳定回答时展示真实正文；仍在生成时展示占位提示，让布局先稳定下来。
 */
const aiAnalysisDisplayText = computed(() => {
  const normalizedAnswer = aiAnalysis.value?.answer.trim() ?? "";
  if (normalizedAnswer) {
    return aiAnalysis.value?.answer ?? "";
  }

  if (aiLoading.value) {
    return "AI 正在根据当前统计窗口生成批次分析，正文会在这里持续流式输出。";
  }

  return "";
});

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
 * 当前工作区的页码信息。
 * 顶部导航和底部翻页按钮都会复用这组结果。
 */
const activeWorkspacePageIndex = computed(() =>
  Math.max(
    STATISTICS_WORKSPACE_PAGE_OPTIONS.findIndex((item) => item.name === activeWorkspacePage.value),
    0,
  ),
);

/**
 * 当前工作区配置。
 */
const activeWorkspacePageConfig = computed(() =>
  STATISTICS_WORKSPACE_PAGE_OPTIONS[activeWorkspacePageIndex.value]
    ?? STATISTICS_WORKSPACE_PAGE_OPTIONS[0],
);

/**
 * 百分比统一转成 1 位小数，保证统计卡片和排行口径一致。
 */
function formatPercentValue(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

/**
 * 切换统计页工作区。
 * 统一收口页内翻页，避免按钮和导航各自维护不同状态。
 */
function goToWorkspacePage(nextPage: StatisticsWorkspacePage): void {
  activeWorkspacePage.value = nextPage;
}

/**
 * 按当前页码顺序翻到上一页或下一页。
 */
function stepWorkspacePage(direction: -1 | 1): void {
  const nextIndex = Math.min(
    Math.max(activeWorkspacePageIndex.value + direction, 0),
    STATISTICS_WORKSPACE_PAGE_OPTIONS.length - 1,
  );
  activeWorkspacePage.value = STATISTICS_WORKSPACE_PAGE_OPTIONS[nextIndex]?.name ?? "overview";
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
 * 处理统计页 AI 继续追问。
 */
async function handleSubmitAiQuestion(): Promise<void> {
  try {
    await submitAiQuestion();
  } catch (caughtError) {
    ElMessage.error(aiError.value || (caughtError instanceof Error ? caughtError.message : "统计 AI 追问失败"));
  }
}

/**
 * 把推荐追问快速填回输入框。
 */
function handleUseSuggestedQuestion(question: string): void {
  useSuggestedQuestion(question);
}

/**
 * 导出海报图时需要把异常转换成用户可读提示。
 */
async function handleExportPng(): Promise<void> {
  try {
    await exportPng();
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "统计海报导出失败");
  }
}

/**
 * 打开 PDF 导出版本选择弹窗。
 */
function handleOpenPdfExportDialog(): void {
  pdfExportDialogVisible.value = true;
}

/**
 * 统计页首屏直接跳到 AI 工作台。
 * 用户不需要再先滚到下半段才能找到 AI 入口。
 */
function handleOpenAiWorkspace(): void {
  goToWorkspacePage("ai");
}

/**
 * 判断首轮分析正文区是否仍贴近底部。
 * 这里保留少量容差，避免浏览器像素取整导致误判。
 */
function isAiAnalysisNearBottom(): boolean {
  const containerElement = aiAnalysisBodyRef.value;
  if (!containerElement) {
    return true;
  }

  const distanceToBottom =
    containerElement.scrollHeight - containerElement.scrollTop - containerElement.clientHeight;
  return distanceToBottom <= 24;
}

/**
 * 响应用户手动滚动首轮分析正文区。
 * 只要用户离开底部，就暂停自动跟随；重新回到底部后再恢复。
 */
function handleAiAnalysisScroll(): void {
  shouldAutoScrollAiAnalysis.value = isAiAnalysisNearBottom();
}

/**
 * 把首轮分析正文区滚动到最新输出位置。
 * 流式分析时只要用户没有主动上翻，就持续自动跟随。
 */
function scrollAiAnalysisToBottom(force = false): void {
  void nextTick(() => {
    if (!force && !shouldAutoScrollAiAnalysis.value) {
      return;
    }

    const containerElement = aiAnalysisBodyRef.value;
    if (!containerElement) {
      return;
    }

    containerElement.scrollTop = containerElement.scrollHeight;
    shouldAutoScrollAiAnalysis.value = true;
  });
}

watch(
  () => aiAnalysis.value?.answer ?? "",
  (nextAnswer) => {
    if (!nextAnswer) {
      shouldAutoScrollAiAnalysis.value = true;
      return;
    }

    scrollAiAnalysisToBottom();
  },
  {
    flush: "post",
  },
);

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
        <ElButton plain :disabled="!hasOverview" @click="handleOpenAiWorkspace">AI 工作台</ElButton>
        <ElButton plain :disabled="!hasOverview" @click="handleExportPng">导出海报图</ElButton>
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
      <section class="app-panel stats-workspace-pager">
        <div class="stats-workspace-pager__header">
          <div>
            <strong>分页工作区</strong>
            <p class="muted-text">
              当前统计页按“总览 / 风险 / 图库 / AI”拆成独立页面。屏幕上只展示当前页，避免一整页越拖越长；打印时会自动把全部页展开。
            </p>
          </div>
          <ElTag effect="dark" round type="info">
            第 {{ activeWorkspacePageIndex + 1 }} / {{ STATISTICS_WORKSPACE_PAGE_OPTIONS.length }} 页
          </ElTag>
        </div>

        <div class="stats-workspace-pager__grid">
          <button
            v-for="(item, index) in STATISTICS_WORKSPACE_PAGE_OPTIONS"
            :key="item.name"
            type="button"
            class="stats-workspace-pager__item"
            :class="{ 'stats-workspace-pager__item--active': activeWorkspacePage === item.name }"
            @click="goToWorkspacePage(item.name)"
          >
            <span class="stats-workspace-pager__item-index">0{{ index + 1 }}</span>
            <strong>{{ item.title }}</strong>
            <span>{{ item.description }}</span>
          </button>
        </div>

        <div class="stats-workspace-pager__footer">
          <div>
            <strong>{{ activeWorkspacePageConfig.title }}</strong>
            <p class="muted-text">{{ activeWorkspacePageConfig.description }}</p>
          </div>
          <div class="stats-workspace-pager__actions">
            <ElButton
              plain
              :disabled="activeWorkspacePageIndex <= 0"
              @click="stepWorkspacePage(-1)"
            >
              上一页
            </ElButton>
            <ElButton
              type="primary"
              plain
              :disabled="activeWorkspacePageIndex >= STATISTICS_WORKSPACE_PAGE_OPTIONS.length - 1"
              @click="stepWorkspacePage(1)"
            >
              下一页
            </ElButton>
          </div>
        </div>
      </section>

      <div class="stats-page__workspace-stage">
        <div
          class="stats-workspace-page"
          :class="{ 'stats-workspace-page--active': activeWorkspacePage === 'overview' }"
          data-workspace-page="overview"
        >
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
            </section>
          </div>
        </div>

        <div
          class="stats-workspace-page"
          :class="{ 'stats-workspace-page--active': activeWorkspacePage === 'ranking' }"
          data-workspace-page="ranking"
        >
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
        </div>

        <div
          class="stats-workspace-page"
          :class="{ 'stats-workspace-page--active': activeWorkspacePage === 'gallery' }"
          data-workspace-page="gallery"
        >
          <StatisticsSampleGallerySummarySection
            :gallery="sampleGallery"
            :filters="overview?.filters ?? null"
          />
        </div>

        <div
          class="stats-workspace-page"
          :class="{ 'stats-workspace-page--active': activeWorkspacePage === 'ai' }"
          data-workspace-page="ai"
        >
          <section class="app-panel stats-ai-panel">
            <div class="stats-panel__header">
              <div>
                <strong>AI 统计工作台</strong>
                <p class="muted-text">
                  AI 会直接读取当前统计窗口的摘要、趋势、缺陷分布、零件/设备排行和关键发现。你可以先生成一轮批次分析，再继续追问，也可以直接围绕当前窗口提问题。
                </p>
              </div>
              <div class="stats-ai-panel__header-tags">
                <ElTag
                  :type="canUseAiAnalysis ? 'success' : 'warning'"
                  effect="dark"
                  round
                >
                  {{ canUseAiAnalysis ? "当前账号已开通 AI 分析" : "当前账号未开通 AI 分析" }}
                </ElTag>
                <ElTag
                  v-if="activeRuntimeModel"
                  effect="dark"
                  round
                  type="success"
                >
                  {{ activeRuntimeModel.displayName }}
                </ElTag>
              </div>
            </div>

            <ElAlert
              v-if="!canUseAiAnalysis"
              type="warning"
              show-icon
              :closable="false"
              title="当前账号未开通统计 AI 分析"
              description="你仍然可以查看图表、筛选数据和导出纯统计报表，但无法发起 AI 分析或继续追问。请联系管理员在系统设置中开启该权限。"
            />

            <div class="stats-ai-panel__controls">
              <ElSelect
                v-model="selectedModelId"
                clearable
                filterable
                :loading="referenceLoading"
                :disabled="!canUseAiAnalysis"
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
                :disabled="!canUseAiAnalysis"
                placeholder="可补充本轮特别关注点，例如：重点分析某零件是否存在持续恶化，或判断问题更像设备侧异常还是材料批次异常。"
              />

              <div class="stats-ai-panel__actions">
                <ElButton
                  type="primary"
                  :loading="aiLoading"
                  :disabled="!canUseAiAnalysis || !hasOverview || isAiStreaming"
                  @click="handleRunAiAnalysis"
                >
                  生成 AI 分析
                </ElButton>
                <span class="muted-text">
                  {{
                    !canUseAiAnalysis
                      ? "当前账号未开通 AI 分析权限。"
                      : activeRuntimeModel
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
              title="统计 AI 工作台请求失败"
              :description="aiError"
            />

            <div class="stats-ai-panel__result">
              <div class="stats-ai-panel__result-meta">
                <span>状态：{{ aiAnalysis?.status ?? (isAiStreaming ? "streaming" : "未生成") }}</span>
                <span>模型：{{ aiAnalysis?.providerHint ?? activeRuntimeModel?.displayName ?? "未生成" }}</span>
                <span>时间：{{ aiAnalysis ? formatDateTime(aiAnalysis.generatedAt) : "未生成" }}</span>
              </div>

              <div class="stats-ai-panel__result-body">
                {{
                  aiAnalysis
                    ? "最近一轮批次分析已经在上方正文区生成。下方多轮追问区只显示你后续真正发起的追问记录，导出 PDF 时也会优先复用这轮分析结果。"
                    : isAiStreaming
                    ? "AI 已开始流式输出，本轮回答会先写入上方分析正文区。"
                    : "当前还没有生成统计 AI 分析。你可以先生成一轮批次分析，或直接在下方输入问题。"
                }}
              </div>
            </div>

            <div
              v-if="shouldShowAiAnalysisBlock"
              class="stats-ai-panel__analysis-block"
            >
              <div class="stats-ai-panel__analysis-header">
                <strong>本轮 AI 批次分析</strong>
                <span class="muted-text">这里直接显示当前批次分析正文，导出和浏览器打印时也会保留。</span>
              </div>
              <div
                ref="aiAnalysisBodyRef"
                :class="[
                  'stats-ai-panel__analysis-body',
                  { 'stats-ai-panel__analysis-body--pending': !aiAnalysis?.answer?.trim() },
                ]"
                @scroll="handleAiAnalysisScroll"
              >
                {{ aiAnalysisDisplayText }}
              </div>
            </div>

            <div
              class="stats-ai-panel__conversation"
              :class="{ 'stats-ai-panel__conversation--empty': visibleAiMessages.length === 0 }"
            >
              <div class="stats-ai-panel__conversation-header">
                <div>
                  <strong>多轮追问</strong>
                  <p class="muted-text">所有追问都会继续绑定当前统计窗口和上方对话历史，不会脱离当前批次单独回答。</p>
                </div>
              </div>

              <ElScrollbar
                v-if="visibleAiMessages.length > 0"
                ref="aiMessagesScrollbarRef"
                class="stats-ai-panel__messages"
                @scroll="handleAiMessagesScroll"
              >
                <div class="stats-ai-panel__message-list">
                  <article
                    v-for="message in visibleAiMessages"
                    :key="message.localId"
                    class="stats-ai-panel__message-row"
                  >
                    <div
                      :class="[
                        'stats-ai-panel__message',
                        message.role === 'assistant'
                          ? 'stats-ai-panel__message--assistant'
                          : 'stats-ai-panel__message--user',
                      ]"
                    >
                      <div class="stats-ai-panel__message-meta">
                        <strong>{{ message.role === "assistant" ? "AI 助理" : "你" }}</strong>
                        <span>
                          {{
                            message.role === "assistant" &&
                            isAiStreaming &&
                            message.localId === streamingAssistantMessageId
                              ? message.content
                                ? "流式输出中"
                                : "思考中"
                              : formatDateTime(message.createdAt)
                          }}
                        </span>
                      </div>

                      <div
                        v-if="
                          message.role === 'assistant' &&
                          isAiStreaming &&
                          message.localId === streamingAssistantMessageId
                        "
                        class="stats-ai-panel__thinking-indicator"
                        aria-label="AI 正在思考"
                      >
                        <span class="stats-ai-panel__thinking-dot" />
                        <span class="stats-ai-panel__thinking-dot" />
                        <span class="stats-ai-panel__thinking-dot" />
                      </div>

                      <div class="stats-ai-panel__message-content">
                        {{ message.content || " " }}
                      </div>
                    </div>
                  </article>
                </div>
              </ElScrollbar>

              <div v-else class="stats-ai-panel__empty-state">
                <ElEmpty
                  :description="aiAnalysis ? '当前还没有追问记录。首轮分析已经显示在上方，继续输入问题即可开始追问。' : '先生成一轮批次分析，或直接在下方输入问题开始追问。'"
                />
              </div>
            </div>

            <div class="stats-ai-panel__question-bank">
              <span class="muted-text">推荐追问</span>
              <div class="stats-ai-panel__question-bank-actions">
                <ElButton
                  v-for="question in aiSuggestedQuestions"
                  :key="question"
                  size="small"
                  plain
                  round
                  @click="handleUseSuggestedQuestion(question)"
                >
                  {{ question }}
                </ElButton>
              </div>
            </div>

            <ElInput
              v-model="aiQuestion"
              type="textarea"
              :rows="4"
              resize="none"
              :disabled="!canUseAiAnalysis"
              placeholder="继续问当前统计窗口的问题，例如：这批次更像设备异常还是材料批次异常？为什么这样判断？"
              @keydown.ctrl.enter.prevent="handleSubmitAiQuestion"
            />

            <div class="stats-ai-panel__submit-bar">
              <div class="stats-ai-panel__submit-meta">
                <span class="muted-text">按 Ctrl + Enter 发送。追问会自动带上当前统计窗口和上方对话历史。</span>
                <span class="muted-text">
                  {{
                    !canUseAiAnalysis
                      ? "当前账号未开通 AI 分析权限。"
                      : activeRuntimeModel
                      ? `当前追问模型：${activeRuntimeModel.displayName} / ${activeRuntimeModel.gatewayName}`
                      : "未选择模型时，后端只会返回预留提示。"
                  }}
                </span>
              </div>

              <div class="stats-ai-panel__submit-actions">
                <ElButton
                  type="primary"
                  :loading="chatSending"
                  :disabled="!canUseAiAnalysis || !aiQuestion.trim() || isAiStreaming"
                  @click="handleSubmitAiQuestion"
                >
                  发送追问
                </ElButton>
              </div>
            </div>
          </section>
        </div>
      </div>
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
  --stats-workspace-stage-height: clamp(620px, calc(100vh - 320px), 920px);
  gap: 22px;
}

.stats-page__hero,
.stats-filter-card__header,
.stats-filter-card__quick-range,
.stats-panel__header,
.stats-ai-panel__header-tags,
.stats-ai-panel__actions,
.stats-ai-panel__conversation-header,
.stats-ai-panel__submit-bar,
.stats-ai-panel__submit-actions,
.stats-page__hero-actions,
.stats-ranking__meta,
.stats-ranking__summary,
.stats-distribution-card__item,
.stats-workspace-pager__header,
.stats-workspace-pager__footer,
.stats-ai-panel__analysis-header {
  display: flex;
  gap: 14px;
}

.stats-page__hero,
.stats-filter-card__header,
.stats-panel__header,
.stats-ai-panel__actions,
.stats-ai-panel__conversation-header,
.stats-ai-panel__submit-bar,
.stats-ranking__meta,
.stats-distribution-card__item,
.stats-workspace-pager__header,
.stats-workspace-pager__footer,
.stats-ai-panel__analysis-header {
  align-items: flex-start;
  justify-content: space-between;
}

.stats-ai-panel__header-tags {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.stats-page__hero,
.stats-filter-card__controls,
.stats-page__hero-actions,
.stats-trend__legend,
.stats-distribution-grid,
.stats-page__chart-grid,
.stats-page__insight-grid,
.stats-page__ranking-grid,
.stats-workspace-pager__grid {
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

.stats-ai-panel {
  min-height: 100%;
}

.stats-filter-card,
.stats-panel,
.stats-ai-panel,
.stats-bars,
.stats-findings,
.stats-ranking,
.stats-ai-panel__controls,
.stats-ai-panel__result,
.stats-ai-panel__conversation,
.stats-ai-panel__question-bank,
.stats-ai-panel__submit-meta {
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
  align-content: start;
}

.stats-workspace-pager {
  padding: 22px;
  display: grid;
  gap: 16px;
}

.stats-workspace-pager__header p,
.stats-workspace-pager__footer p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-workspace-pager__grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stats-workspace-pager__item {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.025);
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.stats-workspace-pager__item:hover {
  transform: translateY(-1px);
  border-color: rgba(127, 228, 208, 0.28);
}

.stats-workspace-pager__item--active {
  border-color: rgba(127, 228, 208, 0.46);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 38%),
    rgba(255, 255, 255, 0.04);
}

.stats-workspace-pager__item-index {
  color: rgba(127, 228, 208, 0.86);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.stats-workspace-pager__item strong {
  font-size: 15px;
  line-height: 1.4;
}

.stats-workspace-pager__item span {
  color: var(--app-text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.stats-workspace-pager__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.stats-page__workspace-stage {
  display: grid;
  gap: 20px;
  min-height: var(--stats-workspace-stage-height);
}

.stats-workspace-page {
  display: none;
  gap: 20px;
  align-content: start;
  min-height: var(--stats-workspace-stage-height);
  max-height: var(--stats-workspace-stage-height);
  overflow-y: auto;
  padding-right: 6px;
}

.stats-workspace-page--active {
  display: grid;
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

.stats-ai-panel__thinking-dot {
  width: 8px;
  height: 8px;
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

.stats-ai-panel__analysis-block {
  display: grid;
  gap: 12px;
  padding: 22px;
  margin-bottom: 4px;
  border-radius: 18px;
  border: 1px solid rgba(127, 228, 208, 0.16);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 34%),
    rgba(255, 255, 255, 0.025);
}

.stats-ai-panel__analysis-body {
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--app-text);
  max-height: min(28vh, 280px);
  overflow-y: auto;
  padding-right: 6px;
}

.stats-ai-panel__analysis-body--pending {
  display: grid;
  align-content: center;
  min-height: 88px;
  max-height: 88px;
  overflow: hidden;
  padding-right: 0;
  color: var(--app-text-secondary);
}

.stats-ai-panel__conversation {
  padding: 22px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.1);
  background: rgba(255, 255, 255, 0.02);
  grid-template-rows: auto minmax(0, 1fr);
}

.stats-ai-panel__conversation--empty {
  grid-template-rows: auto auto;
}

.stats-ai-panel__conversation-header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-ai-panel__messages {
  min-height: 240px;
  max-height: min(34vh, 360px);
  height: auto;
  padding-right: 6px;
}

.stats-ai-panel__empty-state {
  min-height: 160px;
  display: grid;
  place-items: center;
  padding: 8px 0 4px;
}

.stats-ai-panel__message-list {
  display: grid;
  gap: 14px;
}

.stats-ai-panel__message-row {
  display: flex;
}

.stats-ai-panel__message {
  max-width: 90%;
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
}

.stats-ai-panel__message--assistant {
  background: rgba(255, 255, 255, 0.03);
}

.stats-ai-panel__message--user {
  margin-left: auto;
  background: rgba(47, 182, 162, 0.12);
  border-color: rgba(47, 182, 162, 0.22);
}

.stats-ai-panel__message-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--app-text-secondary);
}

.stats-ai-panel__message-content {
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--app-text);
}

.stats-ai-panel__thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stats-ai-panel__question-bank {
  gap: 10px;
}

.stats-ai-panel__question-bank-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.stats-ai-panel__submit-bar {
  gap: 16px;
  padding-top: 4px;
  border-top: 1px solid rgba(149, 184, 223, 0.12);
}

.stats-ai-panel__submit-meta {
  gap: 6px;
}

.stats-ai-panel__submit-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

:deep(.stats-ai-panel__question-bank-actions .el-button) {
  margin-left: 0;
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
  .stats-filter-card__controls,
  .stats-workspace-pager__grid {
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
  .stats-page {
    --stats-workspace-stage-height: auto;
  }

  .stats-page__hero {
    grid-template-columns: 1fr;
  }

  .stats-trend__summary,
  .stats-page__hero-actions,
  .stats-filter-card__header,
  .stats-panel__header,
  .stats-ai-panel__header-tags,
  .stats-ai-panel__actions,
  .stats-ai-panel__conversation-header,
  .stats-ai-panel__submit-bar,
  .stats-ranking__meta,
  .stats-distribution-card__item,
  .stats-workspace-pager__header,
  .stats-workspace-pager__footer,
  .stats-ai-panel__analysis-header {
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

  .stats-ai-panel__message {
    max-width: 100%;
  }

  .stats-page__workspace-stage,
  .stats-workspace-page {
    min-height: auto;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .stats-ai-panel__analysis-body,
  .stats-ai-panel__messages {
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }
}

@media print {
  .stats-page {
    gap: 12px;
  }

  .stats-page__hero-actions,
  .stats-filter-card__quick-range,
  .stats-filter-card__controls,
  .stats-workspace-pager,
  .stats-ai-panel__controls,
  .stats-ai-panel__question-bank,
  .stats-ai-panel__submit-bar {
    display: none !important;
  }

  .stats-page__metrics,
  .stats-page__chart-grid,
  .stats-page__insight-grid,
  .stats-page__ranking-grid,
  .stats-distribution-grid {
    grid-template-columns: 1fr !important;
  }

  .stats-workspace-page {
    display: grid !important;
    gap: 16px;
    min-height: auto;
    max-height: none;
    overflow: visible;
    padding-right: 0;
    break-before: page;
    page-break-before: always;
  }

  .stats-workspace-page:first-child {
    break-before: auto;
    page-break-before: auto;
  }

  .stats-ai-panel__messages {
    min-height: auto;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .stats-ai-panel__message {
    max-width: 100%;
  }

  .stats-ai-panel__analysis-body {
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }
}
</style>
