<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  hint: string;
  accent?: "primary" | "success" | "warning" | "danger" | "info";
}>();
</script>

<template>
  <div class="metric-card app-panel" :data-accent="accent ?? 'primary'">
    <span class="metric-card__label">{{ label }}</span>
    <strong class="metric-card__value">{{ value }}</strong>
    <span class="metric-card__hint">{{ hint }}</span>
  </div>
</template>

<style scoped>
.metric-card {
  position: relative;
  display: grid;
  gap: 12px;
  min-height: 144px;
  padding: 22px;
  overflow: hidden;
}

.metric-card::after {
  content: "";
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 4px;
  background: var(--accent-color, var(--app-primary));
}

.metric-card[data-accent="primary"] {
  --accent-color: var(--app-primary);
}

.metric-card[data-accent="success"] {
  --accent-color: var(--app-success);
}

.metric-card[data-accent="warning"] {
  --accent-color: var(--app-warning);
}

.metric-card[data-accent="danger"] {
  --accent-color: var(--app-danger);
}

.metric-card[data-accent="info"] {
  --accent-color: var(--app-info);
}

.metric-card__label {
  color: var(--app-text-secondary);
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.metric-card__value {
  font-size: 34px;
  line-height: 1;
}

.metric-card__hint {
  color: var(--app-text-secondary);
  font-size: 14px;
}
</style>
