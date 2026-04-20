import type {
  AIChatRequestDto,
  AIChatResponseDto,
  AIReviewRequestDto,
  AIReviewResponseDto,
  DetectionRecordCreateRequestDto,
  DetectionRecordDetailDto,
  DetectionRecordListResponseDto,
  DetectionResult,
  ReviewStatus,
} from "@/types/api";

import { apiRequest, streamSseRequest } from "./client";

export interface RecordListQuery {
  readonly partId?: number;
  readonly deviceId?: number;
  readonly result?: DetectionResult;
  readonly reviewStatus?: ReviewStatus;
  readonly skip?: number;
  readonly limit?: number;
}

/**
 * 获取检测记录列表。
 */
export function fetchRecords(query: RecordListQuery = {}): Promise<DetectionRecordListResponseDto> {
  const params = new URLSearchParams();

  /**
   * 列表页筛选都在这里映射成后端约定的 snake_case 参数。
   */
  if (query.partId !== undefined) {
    params.set("part_id", String(query.partId));
  }
  if (query.deviceId !== undefined) {
    params.set("device_id", String(query.deviceId));
  }
  if (query.result) {
    params.set("result", query.result);
  }
  if (query.reviewStatus) {
    params.set("review_status", query.reviewStatus);
  }
  params.set("skip", String(query.skip ?? 0));
  params.set("limit", String(query.limit ?? 20));
  return apiRequest<DetectionRecordListResponseDto>(`/api/v1/records?${params.toString()}`);
}

/**
 * 获取检测记录详情。
 */
export function fetchRecordDetail(recordId: number): Promise<DetectionRecordDetailDto> {
  return apiRequest<DetectionRecordDetailDto>(`/api/v1/records/${recordId}`);
}

/**
 * 创建新的检测记录。
 * 这里提交的是 MP 侧初检主结果，复核仍然走详情页的单独入口。
 */
export function createRecord(
  payload: DetectionRecordCreateRequestDto,
): Promise<DetectionRecordDetailDto> {
  return apiRequest<DetectionRecordDetailDto>("/api/v1/records", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 触发云端 AI 复核预留接口。
 */
export function requestAiReview(
  recordId: number,
  payload: AIReviewRequestDto,
): Promise<AIReviewResponseDto> {
  return apiRequest<AIReviewResponseDto>(`/api/v1/records/${recordId}/ai-review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 在当前检测记录上下文下发起 AI 对话。
 */
export function requestAiChat(
  recordId: number,
  payload: AIChatRequestDto,
): Promise<AIChatResponseDto> {
  return apiRequest<AIChatResponseDto>(`/api/v1/records/${recordId}/ai-chat`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface AIChatStreamHandlers {
  readonly onMeta?: (payload: AIChatResponseDto) => void;
  readonly onDelta?: (deltaText: string) => void;
  readonly onDone?: (payload: AIChatResponseDto) => void;
}

/**
 * 在当前检测记录上下文下发起流式 AI 对话。
 */
export function streamAiChat(
  recordId: number,
  payload: AIChatRequestDto,
  handlers: AIChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return streamSseRequest(`/api/v1/records/${recordId}/ai-chat/stream`, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
    onEvent: (event) => {
      if (event.event === "meta" && handlers.onMeta) {
        handlers.onMeta(event.data as AIChatResponseDto);
        return;
      }
      if (event.event === "delta" && handlers.onDelta) {
        const payloadData = event.data as { text?: string };
        handlers.onDelta(payloadData.text ?? "");
        return;
      }
      if (event.event === "done" && handlers.onDone) {
        handlers.onDone(event.data as AIChatResponseDto);
      }
    },
  });
}
