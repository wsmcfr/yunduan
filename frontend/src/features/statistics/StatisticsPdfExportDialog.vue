<script setup lang="ts">
import { computed, ref, watch } from "vue";

import AppDialog from "@/components/common/AppDialog.vue";
import type { StatisticsPdfExportMode } from "@/types/api";

const props = defineProps<{
  modelValue: boolean;
  exporting: boolean;
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
  (event: "submit", mode: StatisticsPdfExportMode): void;
}>();

/**
 * PDF 导出版本选项。
 * 这里把标题、说明和性能提示集中成一份静态配置，方便模板和后续文案统一维护。
 */
const PDF_EXPORT_MODE_OPTIONS: Array<{
  mode: StatisticsPdfExportMode;
  title: string;
  description: string;
  performanceHint: string;
  featureHint: string;
}> = [
  {
    mode: "visual",
    title: "视觉版 PDF",
    description: "保留当前页面式卡片、深色面板和更完整的视觉层次，适合演示和汇报。",
    performanceHint: "导出较慢，服务端渲染压力更高。",
    featureHint: "会附带 AI 主分析、追问记录和更多代表图片。",
  },
  {
    mode: "lightweight",
    title: "轻量报表版 PDF",
    description: "改用直接绘制的正式报表布局，导出更快，更适合服务器环境和批量下载。",
    performanceHint: "导出更快，CPU 占用更可控。",
    featureHint: "同样保留 AI 主分析、追问记录和少量代表图片。",
  },
];

/**
 * 当前弹窗中选中的导出版本。
 * 默认仍然落在视觉版，确保历史使用习惯不被强行打断。
 */
const selectedMode = ref<StatisticsPdfExportMode>("visual");

/**
 * 控制弹窗显隐的双向绑定代理。
 */
const visible = computed({
  get: () => props.modelValue,
  set: (nextValue: boolean) => {
    emit("update:modelValue", nextValue);
  },
});

/**
 * 每次重新打开弹窗时，把默认选项重置回视觉版。
 * 这样用户每次导出都能明确看到两个版本的差异，而不是延续上一次的隐藏状态。
 */
watch(
  () => props.modelValue,
  (isVisible) => {
    if (isVisible) {
      selectedMode.value = "visual";
    }
  },
);

/**
 * 提交当前选择的导出版本。
 */
function handleSubmit(): void {
  emit("submit", selectedMode.value);
}
</script>

<template>
  <AppDialog
    v-model="visible"
    width="720px"
    destroy-on-close
    title="选择 PDF 导出版本"
  >
    <div class="stats-pdf-export">
      <p class="muted-text stats-pdf-export__intro">
        两个版本都会尽量保留统计页里的 AI 分析、追问记录和部分代表图片，主要差异在版式风格与导出性能。
      </p>

      <ElRadioGroup v-model="selectedMode" class="stats-pdf-export__group">
        <label
          v-for="option in PDF_EXPORT_MODE_OPTIONS"
          :key="option.mode"
          class="stats-pdf-export__option"
          :class="{ 'stats-pdf-export__option--active': selectedMode === option.mode }"
        >
          <ElRadio :value="option.mode" class="stats-pdf-export__radio">
            {{ option.title }}
          </ElRadio>

          <div class="stats-pdf-export__body">
            <p>{{ option.description }}</p>
            <span>{{ option.performanceHint }}</span>
            <span>{{ option.featureHint }}</span>
          </div>
        </label>
      </ElRadioGroup>
    </div>

    <template #footer>
      <div class="stats-pdf-export__footer">
        <ElButton @click="visible = false">取消</ElButton>
        <ElButton type="primary" :loading="exporting" @click="handleSubmit">
          开始导出
        </ElButton>
      </div>
    </template>
  </AppDialog>
</template>

<style scoped>
.stats-pdf-export,
.stats-pdf-export__group {
  display: grid;
  gap: 16px;
}

.stats-pdf-export__intro {
  margin: 0;
  line-height: 1.8;
}

.stats-pdf-export__option {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.025);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background-color 0.2s ease;
}

.stats-pdf-export__option:hover {
  border-color: rgba(127, 228, 208, 0.24);
  transform: translateY(-1px);
}

.stats-pdf-export__option--active {
  border-color: rgba(127, 228, 208, 0.42);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 36%),
    rgba(255, 255, 255, 0.04);
}

.stats-pdf-export__radio {
  align-self: start;
  margin-top: 2px;
}

.stats-pdf-export__body {
  display: grid;
  gap: 8px;
}

.stats-pdf-export__body p,
.stats-pdf-export__body span {
  margin: 0;
  line-height: 1.7;
}

.stats-pdf-export__body p {
  color: var(--app-text);
  font-weight: 600;
}

.stats-pdf-export__body span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.stats-pdf-export__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 720px) {
  .stats-pdf-export__option {
    grid-template-columns: 1fr;
  }
}
</style>
