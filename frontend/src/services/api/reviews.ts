import type { ManualReviewCreateRequestDto, ReviewRecordDto } from "@/types/api";

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
