<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Refresh, SwitchButton } from "@element-plus/icons-vue";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const pageTitle = computed(() => String(route.meta.title ?? "云端检测系统"));
const currentTimeText = ref("");
let currentTimeTimer: number | null = null;

/**
 * 实时刷新顶部时钟。
 * 这里按秒更新，避免用户必须手动刷新页面才能看到当前时间变化。
 */
function updateCurrentTimeText(): void {
  currentTimeText.value = new Date().toLocaleString("zh-CN", {
    hour12: false,
  });
}

function refreshPage(): void {
  void router.go(0);
}

function logout(): void {
  authStore.logout();
  void router.push({ name: "login" });
}

onMounted(() => {
  updateCurrentTimeText();
  currentTimeTimer = window.setInterval(updateCurrentTimeText, 1000);
});

onUnmounted(() => {
  if (currentTimeTimer !== null) {
    window.clearInterval(currentTimeTimer);
  }
});
</script>

<template>
  <header class="app-header app-panel">
    <div class="app-header__meta">
      <span class="app-header__eyebrow">Cloud Console</span>
      <h2 class="app-header__title">{{ pageTitle }}</h2>
    </div>

    <div class="app-header__actions">
      <div class="app-header__time">
        <span class="app-header__time-label">本地时间</span>
        <strong>{{ currentTimeText }}</strong>
      </div>

      <ElButton :icon="Refresh" plain @click="refreshPage">刷新</ElButton>

      <ElDropdown trigger="click">
        <button class="app-header__user" type="button">
          <span class="app-header__user-avatar">
            {{ authStore.currentUser?.displayName?.slice(0, 1) ?? "A" }}
          </span>
          <div class="app-header__user-text">
            <strong>{{ authStore.currentUser?.displayName ?? "未登录" }}</strong>
            <span>{{ authStore.currentUser?.role ?? "guest" }}</span>
          </div>
        </button>

        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem :icon="SwitchButton" @click="logout">退出登录</ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 22px;
}

.app-header__eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.app-header__title {
  margin: 6px 0 0;
  font-size: 24px;
}

.app-header__actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.app-header__time {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.app-header__time-label {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.app-header__user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--app-border);
  border-radius: 999px;
  color: var(--app-text);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
}

.app-header__user-avatar {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(47, 182, 162, 0.22), rgba(106, 167, 255, 0.34));
  font-weight: 800;
}

.app-header__user-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.app-header__user-text span {
  color: var(--app-text-secondary);
  font-size: 12px;
  text-transform: uppercase;
}

@media (max-width: 900px) {
  .app-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .app-header__actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .app-header__time {
    align-items: flex-start;
  }
}
</style>
