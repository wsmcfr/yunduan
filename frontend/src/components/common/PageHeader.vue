<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
  eyebrow?: string;
}>();
</script>

<template>
  <div class="page-header">
    <span v-if="eyebrow" class="page-header__eyebrow">{{ eyebrow }}</span>
    <h1 class="page-header__title">{{ title }}</h1>
    <p class="page-header__description">{{ description }}</p>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
}

.page-header__eyebrow {
  color: var(--app-primary);
  letter-spacing: 0.18em;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.page-header__title {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  overflow-wrap: anywhere;
}

.page-header__description {
  margin: 0;
  min-width: 0;
  max-width: 820px;
  color: var(--app-text-secondary);
  font-size: 15px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

@media (max-width: 520px) {
  /**
   * 移动端页面标题必须收在右侧业务面板内。
   * 长描述使用 anywhere 断行，避免统计页这类长句把 grid 子项撑出 390px 视口。
   */
  .page-header {
    gap: 6px;
  }

  .page-header__eyebrow {
    font-size: 11px;
  }

  .page-header__title {
    font-size: 26px;
    line-height: 1.16;
  }

  .page-header__description {
    max-width: 100%;
    font-size: 14px;
    line-height: 1.65;
  }
}
</style>
