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
  AdminPasswordResetResponseDto,
  ApprovePasswordChangeRequestResponseDto,
  ApiMessageResponseDto,
  SubmitPasswordChangeRequestDto,
  SystemUserAiPermissionUpdateRequestDto,
  SystemUserListResponseDto,
  SystemUserStatusUpdateRequestDto,
  UserPasswordChangeRequestInfoDto,
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

/**
 * 分页拉取系统设置页中的用户列表。
 */
export function fetchSystemUsers(query?: {
  keyword?: string;
  role?: string;
  aiEnabled?: boolean;
  isActive?: boolean;
  skip?: number;
  limit?: number;
}): Promise<SystemUserListResponseDto> {
  const searchParams = new URLSearchParams();

  if (query?.keyword) {
    searchParams.set("keyword", query.keyword);
  }
  if (query?.role) {
    searchParams.set("role", query.role);
  }
  if (query?.aiEnabled !== undefined) {
    searchParams.set("ai_enabled", String(query.aiEnabled));
  }
  if (query?.isActive !== undefined) {
    searchParams.set("is_active", String(query.isActive));
  }
  if (query?.skip !== undefined) {
    searchParams.set("skip", String(query.skip));
  }
  if (query?.limit !== undefined) {
    searchParams.set("limit", String(query.limit));
  }

  const queryString = searchParams.toString();
  return apiRequest<SystemUserListResponseDto>(
    `/api/v1/settings/users${queryString ? `?${queryString}` : ""}`,
  );
}

/**
 * 修改指定用户的 AI 分析使用权限。
 */
export function updateSystemUserAiPermission(
  userId: number,
  payload: SystemUserAiPermissionUpdateRequestDto,
): Promise<void> {
  return apiRequest<void>(`/api/v1/settings/users/${userId}/ai-permission`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/**
 * 修改指定用户的启停状态。
 */
export function updateSystemUserStatus(
  userId: number,
  payload: SystemUserStatusUpdateRequestDto,
): Promise<void> {
  return apiRequest<void>(`/api/v1/settings/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/**
 * 删除指定用户账号。
 */
export function deleteSystemUser(userId: number): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>(`/api/v1/settings/users/${userId}`, {
    method: "DELETE",
  });
}

/**
 * 管理员直接把指定成员密码重置为系统默认临时密码。
 */
export function resetSystemUserPassword(
  userId: number,
): Promise<AdminPasswordResetResponseDto> {
  return apiRequest<AdminPasswordResetResponseDto>(
    `/api/v1/settings/users/${userId}/password-reset`,
    {
      method: "POST",
    },
  );
}

/**
 * 读取当前登录用户的站内改密申请状态。
 */
export function fetchCurrentUserPasswordChangeRequest(): Promise<UserPasswordChangeRequestInfoDto> {
  return apiRequest<UserPasswordChangeRequestInfoDto>("/api/v1/settings/users/me/password-request");
}

/**
 * 由当前登录用户提交站内改密申请。
 */
export function submitCurrentUserPasswordChangeRequest(
  payload: SubmitPasswordChangeRequestDto,
): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>("/api/v1/settings/users/me/password-request", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 批准指定用户的站内改密申请。
 */
export function approveSystemUserPasswordChangeRequest(
  userId: number,
): Promise<ApprovePasswordChangeRequestResponseDto> {
  return apiRequest<ApprovePasswordChangeRequestResponseDto>(
    `/api/v1/settings/users/${userId}/password-request/approve`,
    {
      method: "POST",
    },
  );
}

/**
 * 拒绝指定用户的站内改密申请。
 */
export function rejectSystemUserPasswordChangeRequest(
  userId: number,
): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>(
    `/api/v1/settings/users/${userId}/password-request/reject`,
    {
      method: "POST",
    },
  );
}
