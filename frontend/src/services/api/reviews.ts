import type {
  BoardReviewSyncRequestDto,
  BoardReviewSyncResponseDto,
  ManualReviewCreateRequestDto,
  ReviewRecordDto,
} from "@/types/api";

import { apiRequest } from "./client";

/**
 * 提交人工复核结果。
 * 这条链路只用于用户在详情页对疑似样本做二次确认。
 */
export function createManualReview(
  recordId: number,
  payload: ManualReviewCreateRequestDto,
): Promise<ReviewRecordDto> {
  return apiRequest<ReviewRecordDto>(`/api/v1/records/${recordId}/manual-review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 提交云端复核结果，并由后端代理同步到 STM32MP157 板端历史。
 */
export function syncBoardReview(
  recordId: number,
  payload: BoardReviewSyncRequestDto,
): Promise<BoardReviewSyncResponseDto> {
  return apiRequest<BoardReviewSyncResponseDto>(
    `/api/v1/records/${recordId}/sync-board-review`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
