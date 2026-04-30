<script setup lang="ts">
import AppHeader from "./AppHeader.vue";
import AppSidebar from "./AppSidebar.vue";
</script>

<template>
  <div class="shell">
    <div class="shell__grid">
      <AppSidebar />
      <main class="shell__content">
        <AppHeader />
        <section class="shell__page app-panel">
          <slot />
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  height: 100dvh;
  min-height: 100dvh;
  padding: 20px;
  overflow: hidden;
  background:
    linear-gradient(transparent 23px, var(--app-grid-line) 24px),
    linear-gradient(90deg, transparent 23px, var(--app-grid-line) 24px);
  background-size: 24px 24px;
}

.shell__grid {
  display: flex;
  gap: 18px;
  height: calc(100dvh - 40px);
  min-height: 0;
}

.shell__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
  min-height: 0;
}

.shell__page {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
  padding: 26px;
}

/**
 * 主内容区是唯一的业务页面滚动容器。
 * 外层 shell 固定在一屏内，长表格和详情内容都在右侧面板内部滚动。
 */
:deep(.page-grid) {
  flex: 1;
  width: 100%;
  min-height: 0;
  max-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: 6px;
}

@media (max-width: 1024px) {
  .shell {
    height: 100dvh;
    min-height: 100dvh;
    padding: 12px;
  }

  .shell__grid {
    height: calc(100dvh - 24px);
    min-height: 0;
    flex-direction: column;
  }

  .shell__page {
    min-height: 0;
    padding: 20px;
  }

  :deep(.page-grid) {
    padding-right: 4px;
  }
}

@media print {
  .shell {
    min-height: auto;
    padding: 0;
    background: #ffffff;
  }

  .shell__grid {
    min-height: auto;
    display: block;
  }

  .shell__content {
    display: block;
  }

  .shell__page {
    padding: 0;
    border: none;
    background: transparent;
    box-shadow: none;
  }

  :deep(.sidebar),
  :deep(.app-header) {
    display: none !important;
  }
}
</style>
