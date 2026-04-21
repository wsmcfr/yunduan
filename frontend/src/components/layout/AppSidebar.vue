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

import ContestChipMark from "@/components/branding/ContestChipMark.vue";
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

/**
 * 侧栏底部环境卡片文案。
 * 线上部署时不再显示“本地联调模式”，避免看起来像忘记删除的开发提示。
 */
const runtimeEnvironmentLabel = computed(() => (import.meta.env.DEV ? "开发环境" : "云端控制台"));
const runtimeEnvironmentTitle = computed(() => (import.meta.env.DEV ? "开发代理已启用" : "生产环境在线"));
const runtimeEnvironmentHint = computed(() => (
  import.meta.env.DEV
    ? "当前前端通过开发代理访问后端接口，适合本地联调和功能验证。"
    : "当前页面运行在已部署环境中，可直接使用系统能力和公司级配置。"
));
const runtimeEnvironmentApiTarget = computed(() => (
  import.meta.env.DEV ? "127.0.0.1:8000" : "同域 /api/v1/*"
));
const runtimeEnvironmentHost = computed(() => window.location.host || "未记录主机");

function navigate(routeName: string): void {
  void router.push({ name: routeName });
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar__brand">
      <span class="sidebar__brand-badge">
        <ContestChipMark class="sidebar__brand-mark" />
      </span>
      <div class="sidebar__brand-copy">
        <strong class="sidebar__brand-title">云端检测系统</strong>
        <p class="sidebar__brand-subtitle">第九届嵌入式芯片与系统设计竞赛</p>
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
      <span class="sidebar__footer-label">{{ runtimeEnvironmentLabel }}</span>
      <strong class="sidebar__footer-title">{{ runtimeEnvironmentTitle }}</strong>
      <p class="sidebar__footer-text">
        {{ runtimeEnvironmentHint }}
      </p>
      <div class="sidebar__footer-meta">
        <div class="sidebar__footer-meta-item">
          <span>接口来源</span>
          <strong>{{ runtimeEnvironmentApiTarget }}</strong>
        </div>
        <div class="sidebar__footer-meta-item">
          <span>当前主机</span>
          <strong>{{ runtimeEnvironmentHost }}</strong>
        </div>
      </div>
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
  align-items: flex-start;
  gap: 14px;
}

.sidebar__brand-copy {
  min-width: 0;
}

.sidebar__brand-badge {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  padding: 6px;
  border: 1px solid rgba(149, 184, 223, 0.18);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015)),
    rgba(10, 24, 39, 0.72);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 12px 30px rgba(4, 10, 18, 0.28);
}

.sidebar__brand-mark {
  width: 100%;
  --contest-brand-ink: #76a8dd;
  --contest-brand-core: rgba(239, 247, 255, 0.96);
}

.sidebar__brand-title {
  display: block;
  font-size: 18px;
}

.sidebar__brand-subtitle {
  margin: 4px 0 0;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
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

.sidebar__footer-meta {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.sidebar__footer-meta-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.025);
}

.sidebar__footer-meta-item span {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.sidebar__footer-meta-item strong {
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.5;
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
