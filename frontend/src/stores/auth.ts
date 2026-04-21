import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  fetchCurrentUserRequest,
  loginRequest,
  logoutRequest,
  registerRequest,
} from "@/services/api/auth";
import { mapUserProfileDto } from "@/services/mappers/commonMappers";
import type { UserProfile } from "@/types/models";

export const useAuthStore = defineStore("auth", () => {
  // 正式认证改为服务端 HttpOnly Cookie，因此前端只保留“当前用户是谁”的最小状态。
  const currentUser = ref<UserProfile | null>(null);
  const isReady = ref(false);

  const isAuthenticated = computed(() => currentUser.value !== null);

  /**
   * 登录并同步当前用户信息。
   */
  async function login(account: string, password: string): Promise<void> {
    const response = await loginRequest({
      account,
      password,
    });
    currentUser.value = mapUserProfileDto(response.user);
    isReady.value = true;
  }

  /**
   * 注册并同步当前用户信息。
   */
  async function register(payload: {
    username: string;
    displayName: string;
    email: string;
    password: string;
  }): Promise<void> {
    const response = await registerRequest({
      username: payload.username,
      display_name: payload.displayName,
      email: payload.email,
      password: payload.password,
    });
    currentUser.value = mapUserProfileDto(response.user);
    isReady.value = true;
  }

  /**
   * 拉取后端当前用户信息。
   */
  async function fetchCurrentUser(): Promise<void> {
    const userDto = await fetchCurrentUserRequest();
    currentUser.value = mapUserProfileDto(userDto);
  }

  /**
   * 刷新页面后尝试根据服务端 Cookie 恢复会话。
   */
  async function restoreSession(): Promise<void> {
    if (isReady.value) {
      return;
    }

    try {
      await fetchCurrentUser();
    } catch {
      currentUser.value = null;
    } finally {
      isReady.value = true;
    }
  }

  /**
   * 请求后端清理 Cookie，并同步前端本地状态。
   */
  async function logout(): Promise<void> {
    try {
      await logoutRequest();
    } finally {
      currentUser.value = null;
      isReady.value = true;
    }
  }

  return {
    currentUser,
    isReady,
    isAuthenticated,
    login,
    register,
    fetchCurrentUser,
    restoreSession,
    logout,
  };
});
