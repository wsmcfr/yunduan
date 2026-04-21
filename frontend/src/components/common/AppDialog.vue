<script setup lang="ts">
import { computed, ref, useAttrs, useSlots, watch } from "vue";

defineOptions({
  inheritAttrs: false,
});

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    width?: string;
    top?: string;
    appendToBody?: boolean;
    destroyOnClose?: boolean;
    showFullscreenToggle?: boolean;
  }>(),
  {
    width: "min(920px, calc(100vw - 32px))",
    top: "4vh",
    appendToBody: false,
    destroyOnClose: false,
    showFullscreenToggle: true,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  close: [];
  closed: [];
  open: [];
  opened: [];
}>();

/**
 * 透传调用方额外附加到弹窗上的 Element Plus 属性。
 * 这样各业务弹窗仍然可以继续使用 class、style 等已有入口，而不必重复声明。
 */
const attrs = useAttrs();

/**
 * 用于判断 footer 插槽是否存在。
 * 没有底部操作区时不渲染 footer，避免产生多余的底部留白。
 */
const slots = useSlots();

/**
 * 当前弹窗是否处于全屏态。
 * 所有二次弹窗统一支持“窗口模式 / 全屏模式”快速切换。
 */
const isFullscreen = ref(false);

/**
 * 标题栏辅助提示文案。
 * 普通模式下提示可拖动，全屏模式下提示可以还原，降低用户试错成本。
 */
const headerHint = computed(() =>
  isFullscreen.value
    ? "当前为全屏显示，可点击右上角退出全屏。"
    : "可拖动标题栏移动位置，双击标题栏也可切换全屏。",
);

/**
 * 普通模式沿用调用方传入的宽度；全屏时交给 Element Plus 占满视口。
 */
const resolvedWidth = computed(() => (isFullscreen.value ? "100vw" : props.width));

/**
 * 全屏时不再保留顶部偏移，避免出现顶部留白。
 */
const resolvedTop = computed(() => (isFullscreen.value ? "0" : props.top));

/**
 * 是否存在 footer 插槽。
 * 这里单独抽成计算属性，避免模板中直接访问 slots 带来噪音。
 */
const hasFooterSlot = computed(() => Boolean(slots.footer));

/**
 * 切换全屏状态。
 */
function toggleFullscreen(): void {
  isFullscreen.value = !isFullscreen.value;
}

/**
 * 转发内部弹窗的 v-model 变化。
 * 点击关闭按钮、遮罩或按下 Esc 时，都要把最新显隐状态同步给父组件。
 */
function handleModelValueUpdate(nextValue: boolean): void {
  emit("update:modelValue", nextValue);
  if (!nextValue) {
    isFullscreen.value = false;
  }
}

/**
 * 对外转发关闭事件，并在关闭时恢复为普通窗口模式。
 */
function handleClose(): void {
  isFullscreen.value = false;
  emit("close");
}

/**
 * 对外转发关闭完成事件。
 */
function handleClosed(): void {
  emit("closed");
}

/**
 * 对外转发打开事件。
 */
function handleOpen(): void {
  emit("open");
}

/**
 * 对外转发打开完成事件。
 */
function handleOpened(): void {
  emit("opened");
}

/**
 * 当父层直接把弹窗设为关闭时，同样要清理本地全屏状态。
 * 这样下次重新打开时仍从普通窗口模式开始，避免状态残留。
 */
watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      isFullscreen.value = false;
    }
  },
);
</script>

<template>
  <ElDialog
    v-bind="attrs"
    class="app-dialog"
    :class="{ 'app-dialog--fullscreen': isFullscreen }"
    :model-value="modelValue"
    :title="undefined"
    :width="resolvedWidth"
    :top="resolvedTop"
    :fullscreen="isFullscreen"
    :draggable="!isFullscreen"
    overflow
    :append-to-body="appendToBody"
    :destroy-on-close="destroyOnClose"
    @update:model-value="handleModelValueUpdate"
    @close="handleClose"
    @closed="handleClosed"
    @open="handleOpen"
    @opened="handleOpened"
  >
    <template #header>
      <div class="app-dialog__header" @dblclick="toggleFullscreen">
        <div class="app-dialog__title-group">
          <strong class="app-dialog__title">{{ title }}</strong>
          <span class="app-dialog__hint">{{ headerHint }}</span>
        </div>

        <div v-if="showFullscreenToggle" class="app-dialog__actions">
          <ElButton text size="small" @click.stop="toggleFullscreen">
            {{ isFullscreen ? "退出全屏" : "全屏" }}
          </ElButton>
        </div>
      </div>
    </template>

    <slot />

    <template v-if="hasFooterSlot" #footer>
      <slot name="footer" />
    </template>
  </ElDialog>
</template>
