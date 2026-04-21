import type {
  ApiMessageResponseDto,
  AuthRuntimeOptionsDto,
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
 * 调用注册接口创建账号并直接建立会话。
 */
export function registerRequest(payload: RegisterRequestDto): Promise<AuthSessionResponseDto> {
  return apiRequest<AuthSessionResponseDto>("/api/v1/auth/register", {
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
