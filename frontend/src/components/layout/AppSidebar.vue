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
 * 跳转到指定业务路由。
 *
 * 主要流程：
 * 1. 接收导航配置中的路由名称；
 * 2. 调用 vue-router 进入目标页面；
 * 3. 让当前激活路由计算属性自动驱动高亮状态。
 *
 * @param routeName 导航项绑定的路由名称。
 */
function navigate(routeName: string): void {
  void router.push({ name: routeName });
}
</script>

<template>
  <aside class="sidebar sidebar--compact">
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
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 26px;
  width: var(--app-sidebar-width);
  height: 100%;
  min-height: 0;
  overflow-y: auto;
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
  --contest-brand-ink: var(--app-copper);
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
  border-color: rgba(255, 138, 31, 0.34);
  background: linear-gradient(135deg, rgba(255, 138, 31, 0.18), rgba(32, 42, 51, 0.78));
  transform: translateX(4px);
}

.sidebar__nav-icon {
  width: 18px;
  height: 18px;
}

@media (max-width: 1024px) {
  /**
   * 小屏侧栏只承担页面切换功能，品牌和导航压缩在一行内。
   * 这样既保留一页控制台外壳，又不会让导航完整占据上半屏。
   */
  .sidebar--compact {
    flex-direction: row;
    align-items: center;
    width: 100%;
    height: auto;
    max-height: 92px;
    overflow: hidden;
    padding: 10px 12px;
    gap: 12px;
  }

  .sidebar__nav {
    display: flex;
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 2px;
    scroll-snap-type: x proximity;
  }

  .sidebar__brand {
    flex: 0 0 auto;
    align-items: center;
    gap: 10px;
    max-width: 260px;
  }

  .sidebar__brand-badge {
    width: 42px;
    height: 42px;
    border-radius: 14px;
  }

  .sidebar__brand-title {
    font-size: 16px;
    line-height: 1.25;
  }

  .sidebar__brand-subtitle {
    margin-top: 2px;
    max-width: 180px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .sidebar__nav-item {
    flex: 0 0 auto;
    min-height: 44px;
    padding: 10px 12px;
    border-radius: 14px;
    scroll-snap-align: start;
  }

  .sidebar__nav-item:hover,
  .sidebar__nav-item.is-active {
    transform: translateY(-1px);
  }
}

@media (max-width: 768px) {
  .sidebar--compact {
    max-height: 72px;
    padding: 8px 10px;
  }

  .sidebar__brand-copy {
    display: none;
  }

  .sidebar__brand-badge {
    width: 40px;
    height: 40px;
  }

  .sidebar__nav-item {
    gap: 8px;
    padding: 9px 11px;
    font-size: 13px;
  }
}
</style>
