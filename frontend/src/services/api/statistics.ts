import type {
  DailyTrendResponseDto,
  DefectDistributionResponseDto,
  SummaryStatisticsDto,
} from "@/types/api";

import { apiRequest } from "./client";

/**
 * 获取统计概览。
 */
export function fetchSummaryStatistics(): Promise<SummaryStatisticsDto> {
  return apiRequest<SummaryStatisticsDto>("/api/v1/statistics/summary");
}

/**
 * 获取每日趋势。
 */
export function fetchDailyTrend(days = 7): Promise<DailyTrendResponseDto> {
  return apiRequest<DailyTrendResponseDto>(`/api/v1/statistics/daily-trend?days=${days}`);
}

/**
 * 获取缺陷类型分布。
 */
export function fetchDefectDistribution(): Promise<DefectDistributionResponseDto> {
  return apiRequest<DefectDistributionResponseDto>("/api/v1/statistics/defect-distribution");
}
