import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/services/api/auth", () => ({
  fetchCurrentUserRequest: vi.fn(),
  loginRequest: vi.fn(),
  logoutRequest: vi.fn(),
  registerRequest: vi.fn(),
}));

import { useAuthStore } from "@/stores/auth";
import {
  fetchCurrentUserRequest,
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
  is_active: true,
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
    expect("token" in store).toBe(false);
  });

  it("注册成功后会同步当前用户并标记 ready", async () => {
    vi.mocked(registerRequest).mockResolvedValue({
      session_expires_at: "2026-04-22T09:00:00Z",
      user: demoUserDto,
    });

    const store = useAuthStore();
    await store.register({
      username: "demo-user",
      displayName: "演示用户",
      email: "demo@example.com",
      password: "StrongPass#2026",
    });

    expect(store.isReady).toBe(true);
    expect(store.currentUser?.email).toBe("demo@example.com");
  });

  it("restoreSession 失败时会安全回退为空会话", async () => {
    vi.mocked(fetchCurrentUserRequest).mockRejectedValue(new Error("401"));

    const store = useAuthStore();
    await store.restoreSession();

    expect(store.isReady).toBe(true);
    expect(store.isAuthenticated).toBe(false);
    expect(store.currentUser).toBeNull();
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
