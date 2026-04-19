<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  value: "good" | "bad" | "uncertain" | "pending" | "reviewed" | "ai_reserved" | "online" | "offline" | "fault";
}>();

/**
 * 统一状态标签的显示文案，避免各页面重复硬编码。
 */
const labelMap = {
  good: "良品",
  bad: "坏品",
  uncertain: "待确认",
  pending: "待复核",
  reviewed: "已复核",
  ai_reserved: "AI 预留",
  online: "在线",
  offline: "离线",
  fault: "故障",
} as const;

const typeMap = {
  good: "success",
  bad: "danger",
  uncertain: "warning",
  pending: "warning",
  reviewed: "success",
  ai_reserved: "info",
  online: "success",
  offline: "info",
  fault: "danger",
} as const;

/**
 * 用计算属性包装标签文案和颜色，确保父组件动态切换状态时视图能同步更新。
 */
const label = computed(() => labelMap[props.value]);
const tagType = computed(() => typeMap[props.value]);
</script>

<template>
  <ElTag class="status-tag" :type="tagType" effect="dark" round>
    {{ label }}
  </ElTag>
</template>

<style scoped>
.status-tag {
  border: none;
  font-weight: 600;
}
</style>
