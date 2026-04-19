<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  CollectionTag,
  DataBoard,
  Monitor,
  Setting,
  Tickets,
  TrendCharts,
} from "@element-plus/icons-vue";

import { appNavigationItems } from "@/router/routes";

const route = useRoute();
const router = useRouter();

const iconMap = {
  DataBoard,
  Tickets,
  CollectionTag,
  Monitor,
  TrendCharts,
  Setting,
};

/**
 * 计算当前激活的导航项名称，用于高亮侧栏。
 */
const currentRouteName = computed(() => String(route.name ?? ""));

function navigate(routeName: string): void {
  void router.push({ name: routeName });
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <span class="sidebar__brand-badge">DF</span>
      <div>
        <strong class="sidebar__brand-title">云端检测系统</strong>
        <p class="sidebar__brand-subtitle">工业缺陷检测 MVP</p>
      </div>
    </div>

    <nav class="sidebar__nav">
      <button
        v-for="item in appNavigationItems"
        :key="item.name"
        class="sidebar__nav-item"
        :class="{ 'is-active': currentRouteName === item.name }"
        type="button"
        @click="navigate(item.name)"
      >
        <component :is="iconMap[item.icon as keyof typeof iconMap]" class="sidebar__nav-icon" />
        <span>{{ item.title }}</span>
      </button>
    </nav>

    <div class="sidebar__footer app-panel">
      <span class="sidebar__footer-label">连接状态</span>
      <strong class="sidebar__footer-title">本地联调模式</strong>
      <p class="sidebar__footer-text">
        前端默认通过 Vite 代理转发到
        <code>127.0.0.1:8000</code>
      </p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 26px;
  width: var(--app-sidebar-width);
  padding: 24px 18px 24px 24px;
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.sidebar__brand-badge {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--app-primary), #7fe4d0);
  color: #03211e;
  font-size: 18px;
  font-weight: 900;
}

.sidebar__brand-title {
  display: block;
  font-size: 18px;
}

.sidebar__brand-subtitle {
  margin: 4px 0 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sidebar__nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 16px;
  color: var(--app-text-secondary);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: all 0.2s ease;
}

.sidebar__nav-item:hover,
.sidebar__nav-item.is-active {
  color: var(--app-text);
  border-color: rgba(47, 182, 162, 0.28);
  background: linear-gradient(135deg, rgba(47, 182, 162, 0.18), rgba(21, 47, 70, 0.72));
  transform: translateX(4px);
}

.sidebar__nav-icon {
  width: 18px;
  height: 18px;
}

.sidebar__footer {
  margin-top: auto;
  padding: 18px;
}

.sidebar__footer-label {
  color: var(--app-text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sidebar__footer-title {
  display: block;
  margin-top: 10px;
  font-size: 18px;
}

.sidebar__footer-text {
  margin: 10px 0 0;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.sidebar__footer code {
  color: var(--app-primary);
}

@media (max-width: 1024px) {
  .sidebar {
    width: 100%;
    padding: 18px;
  }

  .sidebar__nav {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .sidebar__nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
