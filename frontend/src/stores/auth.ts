import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  fetchCurrentUserRequest,
  fetchSessionStateRequest,
  loginRequest,
  logoutRequest,
  registerRequest,
} from "@/services/api/auth";
import {
  mapAuthSessionStateDto,
  mapRegisterResponseDto,
  mapUserProfileDto,
} from "@/services/mappers/commonMappers";
import type { RegisterResponse, UserProfile } from "@/types/models";

interface InviteJoinRegisterPayload {
  registerMode: "invite_join";
  username: string;
  displayName: string;
  email: string;
  password: string;
  inviteCode: string;
}

interface CompanyAdminRequestRegisterPayload {
  registerMode: "company_admin_request";
  username: string;
  displayName: string;
  email: string;
  password: string;
  companyName: string;
  companyContactName: string;
  companyNote?: string | null;
}

type RegisterPayload = InviteJoinRegisterPayload | CompanyAdminRequestRegisterPayload;

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
   * 根据不同注册模式处理公开注册。
   * 邀请码入司会直接登录；新公司管理员申请只提交审批，不建立当前会话。
   */
  async function register(payload: RegisterPayload): Promise<RegisterResponse> {
    const response = mapRegisterResponseDto(
      await registerRequest({
        register_mode: payload.registerMode,
        username: payload.username,
        display_name: payload.displayName,
        email: payload.email,
        password: payload.password,
        invite_code: payload.registerMode === "invite_join" ? payload.inviteCode : null,
        company_name:
          payload.registerMode === "company_admin_request" ? payload.companyName : null,
        company_contact_name:
          payload.registerMode === "company_admin_request" ? payload.companyContactName : null,
        company_note:
          payload.registerMode === "company_admin_request"
            ? payload.companyNote ?? null
            : null,
      }),
    );

    if (response.status === "authenticated") {
      currentUser.value = response.user;
    } else {
      currentUser.value = null;
    }
    isReady.value = true;
    return response;
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
      const sessionState = mapAuthSessionStateDto(await fetchSessionStateRequest());
      currentUser.value = sessionState.authenticated ? sessionState.user : null;
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
