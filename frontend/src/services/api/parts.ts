import type {
  PartCreateRequestDto,
  PartListResponseDto,
  PartResponseDto,
  PartUpdateRequestDto,
} from "@/types/api";

import { apiRequest } from "./client";

export interface PartListQuery {
  readonly keyword?: string;
  readonly isActive?: boolean;
  readonly skip?: number;
  readonly limit?: number;
}

/**
 * 获取零件列表。
 */
export function fetchParts(query: PartListQuery = {}): Promise<PartListResponseDto> {
  const params = new URLSearchParams();

  /**
   * 统一在服务层处理查询参数拼装，避免页面各自拼接字符串。
   */
  if (query.keyword) {
    params.set("keyword", query.keyword);
  }
  if (query.isActive !== undefined) {
    params.set("is_active", String(query.isActive));
  }
  params.set("skip", String(query.skip ?? 0));
  params.set("limit", String(query.limit ?? 20));

  return apiRequest<PartListResponseDto>(`/api/v1/parts?${params.toString()}`);
}

/**
 * 创建零件主数据。
 */
export function createPart(payload: PartCreateRequestDto): Promise<PartResponseDto> {
  return apiRequest<PartResponseDto>("/api/v1/parts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 更新指定零件主数据。
 */
export function updatePart(
  partId: number,
  payload: PartUpdateRequestDto,
): Promise<PartResponseDto> {
  return apiRequest<PartResponseDto>(`/api/v1/parts/${partId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
