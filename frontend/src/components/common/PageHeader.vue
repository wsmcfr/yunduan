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
}

.page-header__description {
  margin: 0;
  max-width: 820px;
  color: var(--app-text-secondary);
  font-size: 15px;
  line-height: 1.7;
}
</style>
