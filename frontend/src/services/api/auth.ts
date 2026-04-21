import type {
  ApiMessageResponseDto,
  AuthRuntimeOptionsDto,
  RegisterResponseDto,
  AuthSessionStateDto,
  AuthSessionResponseDto,
  ForgotPasswordRequestDto,
  LoginRequestDto,
  RegisterRequestDto,
  ResetPasswordRequestDto,
  UserProfileDto,
} from "@/types/api";

import { apiRequest } from "./client";

/**
 * 获取认证页运行时能力，例如是否开放注册、是否启用邮件找回。
 */
export function fetchAuthRuntimeOptionsRequest(): Promise<AuthRuntimeOptionsDto> {
  return apiRequest<AuthRuntimeOptionsDto>("/api/v1/auth/runtime-options");
}

/**
 * 调用登录接口建立服务端 Cookie 会话。
 */
export function loginRequest(payload: LoginRequestDto): Promise<AuthSessionResponseDto> {
  return apiRequest<AuthSessionResponseDto>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 调用注册接口创建账号。
 * 邀请码加入公司会直接登录，申请新公司管理员则只返回申请结果。
 */
export function registerRequest(payload: RegisterRequestDto): Promise<RegisterResponseDto> {
  return apiRequest<RegisterResponseDto>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 发起忘记密码流程。
 */
export function forgotPasswordRequest(payload: ForgotPasswordRequestDto): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 提交一次性令牌和新密码，完成重置。
 */
export function resetPasswordRequest(payload: ResetPasswordRequestDto): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 读取当前浏览器上的会话状态。
 * 未登录时也返回 200，便于前端静默恢复会话而不制造 401 噪音。
 */
export function fetchSessionStateRequest(): Promise<AuthSessionStateDto> {
  return apiRequest<AuthSessionStateDto>("/api/v1/auth/session");
}

/**
 * 请求服务端清理当前浏览器上的认证 Cookie。
 */
export function logoutRequest(): Promise<ApiMessageResponseDto> {
  return apiRequest<ApiMessageResponseDto>("/api/v1/auth/logout", {
    method: "POST",
  });
}

/**
 * 获取当前登录用户。
 */
export function fetchCurrentUserRequest(): Promise<UserProfileDto> {
  return apiRequest<UserProfileDto>("/api/v1/auth/me");
}
