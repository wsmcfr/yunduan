import type {
  AIDiscoveredModelListResponseDto,
  AIGatewayDiscoveryPreviewRequestDto,
  AIGatewayCreateRequestDto,
  AIGatewayDto,
  AIGatewayListResponseDto,
  AIGatewayUpdateRequestDto,
  AIModelProfileCreateRequestDto,
  AIModelProfileDto,
  AIModelProfileUpdateRequestDto,
  AIRuntimeModelOptionListResponseDto,
  ApiMessageResponseDto,
} from "@/types/api";

import { apiRequest } from "./client";

/**
 * 获取配置中心中的 AI 网关与模型列表。
 */
export function fetchAIGateways(): Promise<AIGatewayListResponseDto> {
  return apiRequest<AIGatewayListResponseDto>("/api/v1/settings/ai-gateways");
}

/**
 * 创建新的 AI 网关。
 */
export function createAIGateway(payload: AIGatewayCreateRequestDto): Promise<AIGatewayDto> {
  return apiRequest<AIGatewayDto>("/api/v1/settings/ai-gateways", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 更新指定 AI 网关。
 */
export function updateAIGateway(
  gatewayId: number,
  payload: AIGatewayUpdateRequestDto,
): Promise<AIGatewayDto> {
  return apiRequest<AIGatewayDto>(`/api/v1/settings/ai-gateways/${gatewayId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * 删除指定 AI 网关。
 */
export function deleteAIGateway(gatewayId: number): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>(`/api/v1/settings/ai-gateways/${gatewayId}`, {
    method: "DELETE",
  });
}

/**
 * 在指定网关下创建模型配置。
 */
export function createAIModel(
  gatewayId: number,
  payload: AIModelProfileCreateRequestDto,
): Promise<AIModelProfileDto> {
  return apiRequest<AIModelProfileDto>(`/api/v1/settings/ai-gateways/${gatewayId}/models`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 更新指定模型配置。
 */
export function updateAIModel(
  modelId: number,
  payload: AIModelProfileUpdateRequestDto,
): Promise<AIModelProfileDto> {
  return apiRequest<AIModelProfileDto>(`/api/v1/settings/ai-models/${modelId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * 删除指定模型配置。
 */
export function deleteAIModel(modelId: number): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>(`/api/v1/settings/ai-models/${modelId}`, {
    method: "DELETE",
  });
}

/**
 * 根据指定网关的 URL 与密钥自动探测可用模型。
 */
export function fetchDiscoveredGatewayModels(
  gatewayId: number,
): Promise<AIDiscoveredModelListResponseDto> {
  return apiRequest<AIDiscoveredModelListResponseDto>(
    `/api/v1/settings/ai-gateways/${gatewayId}/discovered-models`,
  );
}

/**
 * 根据弹窗内临时填写的 URL 与密钥即时探测模型。
 */
export function previewGatewayModels(
  payload: AIGatewayDiscoveryPreviewRequestDto,
): Promise<AIDiscoveredModelListResponseDto> {
  return apiRequest<AIDiscoveredModelListResponseDto>(
    "/api/v1/settings/ai-gateways/discovery-preview",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/**
 * 获取业务运行时可用的 AI 模型列表。
 */
export function fetchRuntimeAIModels(): Promise<AIRuntimeModelOptionListResponseDto> {
  return apiRequest<AIRuntimeModelOptionListResponseDto>(
    "/api/v1/settings/ai-models/runtime-options",
  );
}
