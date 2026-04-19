import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchCurrentUserRequest, loginRequest } from "@/services/api/auth";
import { mapUserProfileDto } from "@/services/mappers/commonMappers";
import type { UserProfile } from "@/types/models";
import {
  clearStoredAuthToken,
  getStoredAuthToken,
  setStoredAuthToken,
} from "@/utils/storage";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string>(getStoredAuthToken());
  const currentUser = ref<UserProfile | null>(null);
  const isReady = ref(false);

  const isAuthenticated = computed(() => token.value.length > 0 && currentUser.value !== null);

  /**
   * 登录并写入本地会话状态。
   */
  async function login(username: string, password: string): Promise<void> {
    const response = await loginRequest(username, password);
    token.value = response.access_token;
    setStoredAuthToken(response.access_token);
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
   * 恢复本地已保存的令牌，并同步服务端用户信息。
   */
  async function restoreSession(): Promise<void> {
    if (isReady.value) {
      return;
    }

    token.value = getStoredAuthToken();
    if (!token.value) {
      isReady.value = true;
      return;
    }

    try {
      await fetchCurrentUser();
    } catch {
      logout();
    } finally {
      isReady.value = true;
    }
  }

  /**
   * 清理本地会话。
   */
  function logout(): void {
    token.value = "";
    currentUser.value = null;
    clearStoredAuthToken();
    isReady.value = true;
  }

  return {
    token,
    currentUser,
    isReady,
    isAuthenticated,
    login,
    fetchCurrentUser,
    restoreSession,
    logout,
  };
});
