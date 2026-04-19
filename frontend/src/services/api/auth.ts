import type { LoginResponseDto, UserProfileDto } from "@/types/api";

import { apiRequest } from "./client";

/**
 * 调用登录接口获取访问令牌和当前用户信息。
 */
export function loginRequest(username: string, password: string): Promise<LoginResponseDto> {
  return apiRequest<LoginResponseDto>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({
      username,
      password,
    }),
  });
}

/**
 * 获取当前登录用户。
 */
export function fetchCurrentUserRequest(): Promise<UserProfileDto> {
  return apiRequest<UserProfileDto>("/api/v1/auth/me");
}
