import type {
  DailyTrendResponseDto,
  DefectDistributionResponseDto,
  StatisticsAIAnalysisRequestDto,
  StatisticsAIAnalysisResponseDto,
  StatisticsExportPdfRequestDto,
  StatisticsOverviewDto,
  StatisticsSampleGalleryResponseDto,
  SummaryStatisticsDto,
} from "@/types/api";

import { ApiClientError, apiRequest, streamSseRequest } from "./client";

export interface StatisticsOverviewQuery {
  readonly startDate?: string | null;
  readonly endDate?: string | null;
  readonly days?: number;
  readonly partId?: number | null;
  readonly partCategory?: string | null;
  readonly deviceId?: number | null;
}

/**
 * 统一拼装统计接口查询参数。
 * 这样概览页、导出和 AI 分析都可以复用同一份筛选条件映射。
 */
function buildStatisticsQueryString(query: StatisticsOverviewQuery = {}): string {
  const params = new URLSearchParams();

  if (query.startDate) {
    params.set("start_date", query.startDate);
  }
  if (query.endDate) {
    params.set("end_date", query.endDate);
  }
  if (query.days !== undefined) {
    params.set("days", String(query.days));
  }
  if (query.partId !== undefined && query.partId !== null) {
    params.set("part_id", String(query.partId));
  }
  if (query.partCategory) {
    params.set("part_category", query.partCategory);
  }
  if (query.deviceId !== undefined && query.deviceId !== null) {
    params.set("device_id", String(query.deviceId));
  }

  return params.toString();
}

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

/**
 * 获取统计页完整概览。
 */
export function fetchStatisticsOverview(
  query: StatisticsOverviewQuery = {},
): Promise<StatisticsOverviewDto> {
  const queryString = buildStatisticsQueryString(query);
  const path = queryString
    ? `/api/v1/statistics/overview?${queryString}`
    : "/api/v1/statistics/overview";
  return apiRequest<StatisticsOverviewDto>(path);
}

/**
 * 仅获取统计图库数据。
 * 独立图库页只需要图片和分类入口，不需要重复拉整套趋势和排行数据。
 */
export function fetchStatisticsSampleGallery(
  query: StatisticsOverviewQuery = {},
): Promise<StatisticsSampleGalleryResponseDto> {
  const queryString = buildStatisticsQueryString(query);
  const path = queryString
    ? `/api/v1/statistics/sample-gallery?${queryString}`
    : "/api/v1/statistics/sample-gallery";
  return apiRequest<StatisticsSampleGalleryResponseDto>(path);
}

/**
 * 触发统计页 AI 批次分析。
 */
export function requestStatisticsAiAnalysis(
  payload: StatisticsAIAnalysisRequestDto,
): Promise<StatisticsAIAnalysisResponseDto> {
  return apiRequest<StatisticsAIAnalysisResponseDto>("/api/v1/statistics/ai-analysis", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface StatisticsAiAnalysisStreamHandlers {
  readonly onMeta?: (payload: StatisticsAIAnalysisResponseDto) => void;
  readonly onDelta?: (deltaText: string) => void;
  readonly onDone?: (payload: StatisticsAIAnalysisResponseDto) => void;
}

/**
 * 以 SSE 方式流式获取统计页 AI 分析结果。
 */
export function streamStatisticsAiAnalysis(
  payload: StatisticsAIAnalysisRequestDto,
  handlers: StatisticsAiAnalysisStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return streamSseRequest("/api/v1/statistics/ai-analysis/stream", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
    onEvent: (event) => {
      if (event.event === "meta" && handlers.onMeta) {
        handlers.onMeta(event.data as StatisticsAIAnalysisResponseDto);
        return;
      }
      if (event.event === "delta" && handlers.onDelta) {
        const payloadData = event.data as { text?: string };
        handlers.onDelta(payloadData.text ?? "");
        return;
      }
      if (event.event === "done" && handlers.onDone) {
        handlers.onDone(event.data as StatisticsAIAnalysisResponseDto);
      }
    },
  });
}

/**
 * 触发服务端 PDF 导出并直接下载。
 * 这里使用原生 fetch 读取 Blob，避免把 PDF 当成 JSON 处理。
 */
export async function downloadStatisticsPdf(
  payload: StatisticsExportPdfRequestDto,
): Promise<void> {
  const response = await fetch("/api/v1/statistics/export-pdf", {
    method: "POST",
    headers: new Headers({
      "Content-Type": "application/json",
    }),
    credentials: "include",
    body: JSON.stringify(payload),
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJsonResponse = contentType.includes("application/json");
  if (!response.ok) {
    const errorPayload = isJsonResponse ? await response.json() : {};
    throw new ApiClientError(response.status, errorPayload);
  }

  const pdfBlob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = /filename="([^"]+)"/i.exec(contentDisposition);
  const filename = filenameMatch?.[1] ?? `statistics-report-${Date.now()}.pdf`;
  const objectUrl = URL.createObjectURL(pdfBlob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}
