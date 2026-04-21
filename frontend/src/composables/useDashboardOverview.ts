import { computed, onMounted, ref } from "vue";

import {
  fetchStatisticsOverview,
} from "@/services/api/statistics";
import {
  mapStatisticsOverviewDto,
} from "@/services/mappers/commonMappers";
import type {
  DailyTrendItem,
  DefectDistributionItem,
  DeviceQualityItem,
  PartQualityItem,
  ReviewStatusDistributionItem,
  SummaryStatistics,
  StatisticsOverview,
  StatisticsSampleGallery,
} from "@/types/models";

/**
 * 仪表盘组合式逻辑。
 * 统一管理总览、趋势、风险排行和图库摘要，避免仪表盘继续停留在占位表格阶段。
 */
export function useDashboardOverview() {
  /**
   * 当前仪表盘直接复用统计概览接口。
   * 这样仪表盘和统计页使用同一套聚合口径，后续扩展不会再出现两个页面数据对不上。
   */
  const loading = ref(false);
  const error = ref<string>("");
  const overview = ref<StatisticsOverview | null>(null);

  /**
   * 基于统计概览派生出仪表盘各区块所需的数据。
   * 这些计算属性保持只读，页面只负责展示，不再自己拼业务口径。
   */
  const summary = computed<SummaryStatistics | null>(() => overview.value?.summary ?? null);
  const trendItems = computed<DailyTrendItem[]>(() => overview.value?.dailyTrend ?? []);
  const defectItems = computed<DefectDistributionItem[]>(() => overview.value?.defectDistribution ?? []);
  const reviewStatusItems = computed<ReviewStatusDistributionItem[]>(
    () => overview.value?.reviewStatusDistribution ?? [],
  );
  const partRiskItems = computed<PartQualityItem[]>(() => overview.value?.partQualityRanking ?? []);
  const deviceRiskItems = computed<DeviceQualityItem[]>(() => overview.value?.deviceQualityRanking ?? []);
  const sampleGallery = computed<StatisticsSampleGallery | null>(() => overview.value?.sampleGallery ?? null);
  const keyFindings = computed<string[]>(() => overview.value?.keyFindings.slice(0, 4) ?? []);

  /**
   * 风险记录 = 不良 + 待确认。
   * 仪表盘首页更关心需要人介入的压力，不只看单独的不良数。
   */
  const riskRecordCount = computed<number>(() => {
    if (!summary.value) {
      return 0;
    }
    return summary.value.badCount + summary.value.uncertainCount;
  });

  /**
   * 审核完成率用于判断当前闭环进度。
   * 若当前窗口完全没有审核任务，则按 0 处理，避免除零产生 `NaN`。
   */
  const reviewCompletionRate = computed<number>(() => {
    if (!summary.value) {
      return 0;
    }

    const reviewTaskCount = summary.value.reviewedCount + summary.value.pendingReviewCount;
    if (reviewTaskCount <= 0) {
      return 0;
    }
    return summary.value.reviewedCount / reviewTaskCount;
  });

  /**
   * 最近活跃日期优先取“有检测量的最后一天”。
   * 这样不会因为趋势数组最后一天正好是 0，而把用户视线带到无效日期。
   */
  const latestTrend = computed<DailyTrendItem | null>(() => {
    const latestActiveItem = [...trendItems.value].reverse().find((item) => item.totalCount > 0);
    return latestActiveItem ?? trendItems.value[trendItems.value.length - 1] ?? null;
  });

  /**
   * 提炼仪表盘最值得放在顶部的几个焦点。
   * 这些值会直接出现在顶部信息区，帮助用户一眼看到“当前最需要关注什么”。
   */
  const topDefect = computed<DefectDistributionItem | null>(() => defectItems.value[0] ?? null);
  const topPartRisk = computed<PartQualityItem | null>(() => partRiskItems.value[0] ?? null);
  const topDeviceRisk = computed<DeviceQualityItem | null>(() => deviceRiskItems.value[0] ?? null);

  /**
   * 刷新仪表盘数据。
   * 这里统一使用 14 天窗口，兼顾短期波动和当前批次活跃度，不再拆成多个零散接口并行请求。
   */
  async function refresh(): Promise<void> {
    loading.value = true;
    error.value = "";

    try {
      const overviewDto = await fetchStatisticsOverview({ days: 14 });
      overview.value = mapStatisticsOverviewDto(overviewDto);
    } catch (caughtError) {
      error.value = caughtError instanceof Error ? caughtError.message : "仪表盘数据加载失败";
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    void refresh();
  });

  return {
    loading,
    error,
    overview,
    summary,
    trendItems,
    defectItems,
    reviewStatusItems,
    partRiskItems,
    deviceRiskItems,
    sampleGallery,
    keyFindings,
    riskRecordCount,
    reviewCompletionRate,
    latestTrend,
    topDefect,
    topPartRisk,
    topDeviceRisk,
    refresh,
  };
}
