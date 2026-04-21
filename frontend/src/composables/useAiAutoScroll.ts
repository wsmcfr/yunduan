import type { ScrollbarInstance } from "element-plus";
import { nextTick, ref, watch, type Ref } from "vue";

/**
 * 距离底部多近时，仍然视为“用户停留在最新位置”。
 * 预留少量容差，避免浏览器小数像素和滚动条抖动导致误判。
 */
const DEFAULT_BOTTOM_THRESHOLD = 24;

/**
 * AI 消息区自动跟随滚动的配置项。
 * 当前主要服务于单条复检弹窗和统计分析页的多轮对话面板。
 */
export interface UseAiAutoScrollOptions<TMessage> {
  messages: Ref<ReadonlyArray<TMessage>>;
  bottomThreshold?: number;
}

/**
 * 管理 AI 多轮消息区的“自动滚到底部”行为。
 * 规则：
 * 1. 默认自动跟随最新消息。
 * 2. 用户手动上滑离开底部后，暂停自动跟随。
 * 3. 用户重新滑回底部后，后续流式内容继续自动跟随。
 */
export function useAiAutoScroll<TMessage>({
  messages,
  bottomThreshold = DEFAULT_BOTTOM_THRESHOLD,
}: UseAiAutoScrollOptions<TMessage>) {
  const scrollbarRef = ref<ScrollbarInstance | null>(null);
  const shouldAutoScroll = ref(true);

  /**
   * 判断当前滚动位置是否仍然贴近底部。
   * 这里统一从 Element Plus Scrollbar 的 wrap 容器读取实际滚动状态。
   */
  function isNearBottom(): boolean {
    const wrapElement = scrollbarRef.value?.wrapRef;
    if (!wrapElement) {
      return true;
    }

    const distanceToBottom =
      wrapElement.scrollHeight - wrapElement.scrollTop - wrapElement.clientHeight;
    return distanceToBottom <= bottomThreshold;
  }

  /**
   * 把消息区滚动到最底部。
   * `force=true` 时会忽略“用户当前正在上翻”的状态，适用于弹窗重置或首次打开。
   */
  function scrollToBottom(force = false): void {
    void nextTick(() => {
      if (!force && !shouldAutoScroll.value) {
        return;
      }

      const wrapElement = scrollbarRef.value?.wrapRef;
      if (!wrapElement) {
        return;
      }

      scrollbarRef.value?.setScrollTop(wrapElement.scrollHeight);
      shouldAutoScroll.value = true;
    });
  }

  /**
   * 响应用户手动滚动消息区。
   * 只要用户离开底部，就暂停自动跟随；重新滑回底部后则恢复。
   */
  function handleScroll(): void {
    shouldAutoScroll.value = isNearBottom();
  }

  /**
   * 重置自动滚动状态。
   * 用于弹窗切换记录、对话区整体重建等场景，确保新会话默认跟随最新消息。
   */
  function resetAutoScroll(): void {
    shouldAutoScroll.value = true;
    scrollToBottom(true);
  }

  watch(
    messages,
    (nextMessages) => {
      /**
       * 会话被整体清空后，下一轮新消息应该重新默认跟随到底部。
       */
      if (nextMessages.length === 0) {
        shouldAutoScroll.value = true;
        return;
      }

      scrollToBottom();
    },
    {
      deep: true,
      flush: "post",
    },
  );

  return {
    scrollbarRef,
    shouldAutoScroll,
    handleScroll,
    scrollToBottom,
    resetAutoScroll,
  };
}
