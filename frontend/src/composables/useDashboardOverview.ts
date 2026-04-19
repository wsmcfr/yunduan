import { onMounted, ref } from "vue";

import {
  fetchDailyTrend,
  fetchDefectDistribution,
  fetchSummaryStatistics,
} from "@/services/api/statistics";
import {
  mapDailyTrendItemDto,
  mapDefectDistributionItemDto,
  mapSummaryStatisticsDto,
} from "@/services/mappers/commonMappers";
import type {
  DailyTrendItem,
  DefectDistributionItem,
  SummaryStatistics,
} from "@/types/models";

/**
 * 仪表盘组合式逻辑。
 * 统一管理概览、趋势和缺陷分布的加载状态，避免页面脚本继续膨胀。
 */
export function useDashboardOverview() {
  const loading = ref(false);
  const error = ref<string>("");
  const summary = ref<SummaryStatistics | null>(null);
  const trendItems = ref<DailyTrendItem[]>([]);
  const defectItems = ref<DefectDistributionItem[]>([]);

  async function refresh(): Promise<void> {
    loading.value = true;
    error.value = "";

    try {
      const [summaryDto, trendDto, defectDto] = await Promise.all([
        fetchSummaryStatistics(),
        fetchDailyTrend(7),
        fetchDefectDistribution(),
      ]);

      summary.value = mapSummaryStatisticsDto(summaryDto);
      trendItems.value = trendDto.items.map(mapDailyTrendItemDto);
      defectItems.value = defectDto.items.map(mapDefectDistributionItemDto);
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
    summary,
    trendItems,
    defectItems,
    refresh,
  };
}
