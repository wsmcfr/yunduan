import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/services/api/auth", () => ({
  fetchCurrentUserRequest: vi.fn(),
  fetchSessionStateRequest: vi.fn(),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
  registerRequest: vi.fn(),
}));

import { useAuthStore } from "@/stores/auth";
import {
  fetchSessionStateRequest,
  loginRequest,
  logoutRequest,
  registerRequest,
} from "@/services/api/auth";

const demoUserDto = {
  id: 7,
  username: "demo-user",
  email: "demo@example.com",
  display_name: "演示用户",
  role: "operator" as const,
  company: {
    id: 2,
    name: "演示公司",
    is_active: true,
    is_system_reserved: false,
  },
  is_default_admin: false,
  admin_application_status: "not_applicable" as const,
  is_active: true,
  can_use_ai_analysis: false,
  last_login_at: "2026-04-21T09:00:00Z",
  password_changed_at: "2026-04-21T09:00:00Z",
  created_at: "2026-04-21T08:00:00Z",
  updated_at: "2026-04-21T08:30:00Z",
};

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("登录成功后只保存当前用户信息，不再依赖前端 token", async () => {
    vi.mocked(loginRequest).mockResolvedValue({
      session_expires_at: "2026-04-22T09:00:00Z",
      user: demoUserDto,
    });

    const store = useAuthStore();
    await store.login("demo-user", "StrongPass#2026");

    expect(store.isAuthenticated).toBe(true);
    expect(store.currentUser?.username).toBe("demo-user");
    expect(store.currentUser?.canUseAiAnalysis).toBe(false);
    expect("token" in store).toBe(false);
  });

  it("邀请码注册成功后会同步当前用户并标记 ready", async () => {
    vi.mocked(registerRequest).mockResolvedValue({
      status: "authenticated",
      message: "注册成功，已自动登录。",
      session_expires_at: "2026-04-22T09:00:00Z",
      user: demoUserDto,
    });

    const store = useAuthStore();
    const result = await store.register({
      registerMode: "invite_join",
      username: "demo-user",
      displayName: "演示用户",
      email: "demo@example.com",
      password: "StrongPass#2026",
      inviteCode: "INVITE8888",
    });

    expect(store.isReady).toBe(true);
    expect(store.currentUser?.email).toBe("demo@example.com");
    expect(result.status).toBe("authenticated");
  });

  it("申请新公司管理员时不会直接建立会话", async () => {
    vi.mocked(registerRequest).mockResolvedValue({
      status: "application_submitted",
      message: "已提交新公司管理员申请，请等待平台默认管理员审批。",
      session_expires_at: null,
      user: null,
    });

    const store = useAuthStore();
    const result = await store.register({
      registerMode: "company_admin_request",
      username: "new-admin",
      displayName: "新公司管理员",
      email: "admin@example.com",
      password: "StrongPass#2026",
      companyName: "新公司",
      companyContactName: "张三",
      companyNote: "申请开通独立租户",
    });

    expect(store.isReady).toBe(true);
    expect(store.isAuthenticated).toBe(false);
    expect(store.currentUser).toBeNull();
    expect(result.status).toBe("application_submitted");
  });

  it("restoreSession 失败时会安全回退为空会话", async () => {
    vi.mocked(fetchSessionStateRequest).mockRejectedValue(new Error("network"));

    const store = useAuthStore();
    await store.restoreSession();

    expect(store.isReady).toBe(true);
    expect(store.isAuthenticated).toBe(false);
    expect(store.currentUser).toBeNull();
  });

  it("restoreSession 成功时会根据公开会话探针恢复当前用户", async () => {
    vi.mocked(fetchSessionStateRequest).mockResolvedValue({
      authenticated: true,
      user: demoUserDto,
    });

    const store = useAuthStore();
    await store.restoreSession();

    expect(store.isReady).toBe(true);
    expect(store.isAuthenticated).toBe(true);
    expect(store.currentUser?.username).toBe("demo-user");
  });

  it("logout 会请求后端并清空当前用户", async () => {
    vi.mocked(loginRequest).mockResolvedValue({
      session_expires_at: "2026-04-22T09:00:00Z",
      user: demoUserDto,
    });
    vi.mocked(logoutRequest).mockResolvedValue({
      message: "已退出登录。",
    });

    const store = useAuthStore();
    await store.login("demo-user", "StrongPass#2026");
    await store.logout();

    expect(logoutRequest).toHaveBeenCalledTimes(1);
    expect(store.isAuthenticated).toBe(false);
    expect(store.currentUser).toBeNull();
  });
});
