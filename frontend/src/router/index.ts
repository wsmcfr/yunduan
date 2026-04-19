import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

import { routes } from "./routes";

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore();

  /**
   * 首次进入受保护页面时尝试恢复本地会话。
   * 这样浏览器刷新后仍然能继续保留登录状态。
   */
  if (!authStore.isReady) {
    await authStore.restoreSession();
  }

  const requiresAuth = to.meta.requiresAuth !== false;

  if (requiresAuth && !authStore.isAuthenticated) {
    return {
      name: "login",
      query: {
        redirect: to.fullPath,
      },
    };
  }

  if (to.name === "login" && authStore.isAuthenticated) {
    return { name: "dashboard" };
  }

  return true;
});

export default router;
