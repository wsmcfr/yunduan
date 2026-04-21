<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { ArrowLeft, ArrowRight } from "@element-plus/icons-vue";

import AppDialog from "@/components/common/AppDialog.vue";
import { ApiClientError } from "@/services/api/client";
import { streamAiChat } from "@/services/api/records";
import { fetchRuntimeAIModels } from "@/services/api/settings";
import {
  mapAIChatResponseDto,
  mapAIRuntimeModelOptionDto,
} from "@/services/mappers/commonMappers";
import { useAuthStore } from "@/stores/auth";
import type {
  AIChatMessage,
  AIContextFile,
  AIRuntimeModelOption,
  DetectionRecordModel,
} from "@/types/models";
import { formatConfidence, formatDateTime } from "@/utils/format";
import {
  getStoredPreferredRuntimeModelId,
  resolvePreferredRuntimeModelId,
  setStoredPreferredRuntimeModelId,
} from "@/utils/aiModelSelection";
import {
  buildAiPreviewUrl,
  createAiOpeningMessage,
  createDefaultAiSuggestedQuestions,
  getAiFileKindLabel,
  sortAiDisplayFiles,
} from "@/utils/aiReview";

interface AiPreviewFile {
  id: number;
  fileKind: "source" | "annotated" | "thumbnail";
  objectKey: string;
  uploadedAt: string | null;
  previewUrl: string | null;
  label: string;
  sequenceLabel: string;
}

interface BrowserSpeechRecognitionAlternative {
  transcript: string;
}

interface BrowserSpeechRecognitionResult {
  isFinal: boolean;
  length: number;
  [index: number]: BrowserSpeechRecognitionAlternative;
}

interface BrowserSpeechRecognitionResultList {
  length: number;
  [index: number]: BrowserSpeechRecognitionResult;
}

interface BrowserSpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: BrowserSpeechRecognitionResultList;
}

interface BrowserSpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface BrowserSpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: ((event: Event) => void) | null;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onend: ((event: Event) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface BrowserSpeechRecognitionConstructor {
  new (): BrowserSpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  }
}

const props = defineProps<{
  modelValue: boolean;
  record: DetectionRecordModel | null;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
}>();
const authStore = useAuthStore();

/**
 * 输入框中的当前问题。
 */
const question = ref("");

/**
 * 当前对话消息流。
 */
const messages = ref<AIChatMessage[]>([]);

/**
 * 发送状态。
 */
const sending = ref(false);
const runtimeModelsLoading = ref(false);
const runtimeModels = ref<AIRuntimeModelOption[]>([]);
const selectedModelId = ref<number | null>(null);
const runtimeModelsError = ref("");
const chatErrorMessage = ref("");
const speechRecognition = ref<BrowserSpeechRecognition | null>(null);
const speechListening = ref(false);
const speechInterimText = ref("");
const speechBaseQuestion = ref("");
const speechFinalText = ref("");
const activeChatAbortController = ref<AbortController | null>(null);
const streamingAssistantMessageId = ref<string | null>(null);

/**
 * 后端返回的推荐追问。
 */
const suggestedQuestions = ref<string[]>([]);

/**
 * 当前轮 AI 回答实际引用到的文件对象。
 */
const referencedFiles = ref<AIContextFile[]>([]);

/**
 * 当前选中的预览文件编号。
 */
const activePreviewFileId = ref<number | null>(null);

/**
 * 预览文件列表。
 * 这里优先把标注图排前面，便于用户先看 AI 最可能引用的证据图。
 */
const previewFiles = computed<AiPreviewFile[]>(() => {
  if (!props.record?.files) {
    return [];
  }

  const sortedFiles = sortAiDisplayFiles(
    props.record.files.map((file) => ({
      id: file.id,
      fileKind: file.fileKind,
      objectKey: file.objectKey,
      uploadedAt: file.uploadedAt,
      previewUrl: buildAiPreviewUrl(file),
      label: getAiFileKindLabel(file.fileKind),
      sequenceLabel: "",
    })),
  );

  /**
   * 当同一条记录下存在多张同类型图片时，给标签追加序号。
   * 这样顶部按钮和底部页码都能明确告诉用户当前看到的是第几张。
   */
  const totalCountByKind: Record<AiPreviewFile["fileKind"], number> = {
    annotated: 0,
    source: 0,
    thumbnail: 0,
  };
  const currentCountByKind: Record<AiPreviewFile["fileKind"], number> = {
    annotated: 0,
    source: 0,
    thumbnail: 0,
  };

  for (const file of sortedFiles) {
    totalCountByKind[file.fileKind] += 1;
  }

  return sortedFiles.map((file) => {
    currentCountByKind[file.fileKind] += 1;
    const sameKindTotal = totalCountByKind[file.fileKind];

    return {
      ...file,
      sequenceLabel:
        sameKindTotal > 1 ? `${file.label} ${currentCountByKind[file.fileKind]}` : file.label,
    };
  });
});

/**
 * 当前正在展示的大图文件。
 */
const activePreviewFile = computed<AiPreviewFile | null>(() => {
  if (previewFiles.value.length === 0) {
    return null;
  }

  return (
    previewFiles.value.find((file) => file.id === activePreviewFileId.value) ??
    previewFiles.value[0]
  );
});

/**
 * 当前是否存在多张可切换的预览图。
 * 只有多图时才展示左右切换按钮和页码，避免单图场景出现无意义控件。
 */
const hasMultiplePreviewFiles = computed(() => previewFiles.value.length > 1);

/**
 * 当前大图在预览列表中的位置。
 * 用于计算“第几张 / 共几张”的提示，以及左右切换后的目标索引。
 */
const activePreviewIndex = computed(() => {
  if (!activePreviewFile.value) {
    return -1;
  }

  return previewFiles.value.findIndex((file) => file.id === activePreviewFile.value?.id);
});

/**
 * 当前预览页码文案。
 */
const activePreviewPageText = computed(() => {
  if (previewFiles.value.length === 0 || activePreviewIndex.value < 0) {
    return "0 / 0";
  }

  return `${activePreviewIndex.value + 1} / ${previewFiles.value.length}`;
});

/**
 * 当前选中的运行时模型配置。
 */
const activeRuntimeModel = computed<AIRuntimeModelOption | null>(() => {
  if (selectedModelId.value === null) {
    return null;
  }

  return runtimeModels.value.find((item) => item.id === selectedModelId.value) ?? null;
});

/**
 * 当前账号是否具备 AI 对话使用权限。
 */
const canUseAiAnalysis = computed(() => authStore.currentUser?.canUseAiAnalysis ?? false);

/**
 * 当前浏览器是否支持语音识别。
 * 这里优先兼容标准接口和 Chromium 常见的 `webkitSpeechRecognition`。
 */
const speechRecognitionSupported = computed(() => {
  if (typeof window === "undefined") {
    return false;
  }

  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
});

/**
 * 获取浏览器内建语音识别构造函数。
 */
function getSpeechRecognitionConstructor(): BrowserSpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/**
 * 把基准文本和语音识别结果拼成最终问题。
 */
function mergeSpeechQuestion(baseText: string, nextText: string): string {
  const normalizedParts = [baseText.trim(), nextText.trim()].filter(Boolean);
  return normalizedParts.join(" ");
}

/**
 * 生成一条本地消息唯一 ID。
 * 这里优先使用浏览器原生 UUID，回退时再拼接时间戳与随机串，避免消息主键碰撞。
 */
function createLocalMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * 统一创建对话消息。
 * 每条消息都会补齐本地唯一 ID 和创建时间，避免各处手写时遗漏字段。
 */
function createChatMessage(role: AIChatMessage["role"], content: string): AIChatMessage {
  return {
    localId: createLocalMessageId(),
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

/**
 * 重置语音识别中间状态。
 */
function resetSpeechState(): void {
  speechInterimText.value = "";
  speechBaseQuestion.value = "";
  speechFinalText.value = "";
}

/**
 * 初始化弹窗状态。
 * 每次打开弹窗或切换记录时，都重新基于当前记录生成一轮新的上下文会话。
 */
function resetDialogState(): void {
  abortActiveChatStream();
  question.value = "";
  referencedFiles.value = [];
  chatErrorMessage.value = "";
  runtimeModelsError.value = "";
  cleanupVoiceInput();

  if (!props.record) {
    messages.value = [];
    suggestedQuestions.value = [];
    activePreviewFileId.value = null;
    return;
  }

  messages.value = [
    createChatMessage("assistant", createAiOpeningMessage(props.record)),
  ];
  suggestedQuestions.value = createDefaultAiSuggestedQuestions(props.record);
  activePreviewFileId.value = previewFiles.value[0]?.id ?? null;
}

/**
 * 拉取后端当前可用的运行时模型列表。
 */
async function loadRuntimeModels(): Promise<void> {
  if (!canUseAiAnalysis.value) {
    runtimeModels.value = [];
    selectedModelId.value = null;
    runtimeModelsError.value = "";
    return;
  }

  runtimeModelsLoading.value = true;
  runtimeModelsError.value = "";

  try {
    const response = await fetchRuntimeAIModels();
    runtimeModels.value = response.items.map(mapAIRuntimeModelOptionDto);
    selectedModelId.value = resolvePreferredRuntimeModelId(
      runtimeModels.value,
      getStoredPreferredRuntimeModelId(),
    );
    setStoredPreferredRuntimeModelId(selectedModelId.value);
  } catch (caughtError) {
    runtimeModels.value = [];
    selectedModelId.value = null;
    runtimeModelsError.value =
      caughtError instanceof Error ? caughtError.message : "运行时模型列表加载失败";
  } finally {
    runtimeModelsLoading.value = false;
  }
}

/**
 * 关闭弹窗。
 */
function closeDialog(): void {
  abortActiveChatStream();
  cleanupVoiceInput();
  emit("update:modelValue", false);
}

/**
 * 将推荐问题一键回填到输入框。
 */
function useSuggestedQuestion(suggestedQuestion: string): void {
  question.value = suggestedQuestion;
}

/**
 * 手动切换当前预览文件。
 * 顶部文件按钮和左右箭头都会复用这里，确保切换入口行为一致。
 */
function activatePreviewFile(fileId: number): void {
  activePreviewFileId.value = fileId;
}

/**
 * 按相对步长循环切换预览图。
 * 例如 `-1` 表示上一张，`1` 表示下一张，到边界后会回到另一端继续循环。
 */
function switchPreviewFile(offset: number): void {
  if (previewFiles.value.length === 0) {
    return;
  }

  const currentIndex = activePreviewIndex.value >= 0 ? activePreviewIndex.value : 0;
  const nextIndex =
    (currentIndex + offset + previewFiles.value.length) % previewFiles.value.length;

  activePreviewFileId.value = previewFiles.value[nextIndex].id;
}

/**
 * 切到上一张预览图。
 */
function showPreviousPreviewFile(): void {
  switchPreviewFile(-1);
}

/**
 * 切到下一张预览图。
 */
function showNextPreviewFile(): void {
  switchPreviewFile(1);
}

/**
 * 释放当前语音识别实例。
 * 关闭弹窗、切换记录或组件卸载时都要主动清理，避免浏览器继续占用麦克风。
 */
function cleanupVoiceInput(): void {
  if (speechRecognition.value) {
    speechRecognition.value.onstart = null;
    speechRecognition.value.onresult = null;
    speechRecognition.value.onerror = null;
    speechRecognition.value.onend = null;
    speechRecognition.value.abort();
    speechRecognition.value = null;
  }

  speechListening.value = false;
  resetSpeechState();
}

/**
 * 主动中止当前 AI 流式对话。
 * 关闭弹窗、切换记录或重新发起请求前都要先清理，避免旧流继续回写到当前界面。
 */
function abortActiveChatStream(): void {
  activeChatAbortController.value?.abort();
  activeChatAbortController.value = null;
  streamingAssistantMessageId.value = null;
  sending.value = false;
}

/**
 * 手动停止当前语音识别。
 */
function stopVoiceInput(): void {
  speechRecognition.value?.stop();
}

/**
 * 将 AI 对话接口错误转换成更易理解的提示语。
 * 这里优先把后端已经返回的供应商错误细节展开，避免前端只看到笼统的 HTTP 401。
 */
function getAiChatRequestErrorMessage(caughtError: unknown): string {
  if (!(caughtError instanceof ApiClientError)) {
    return caughtError instanceof Error ? caughtError.message : "AI 对话调用失败";
  }

  if (
    caughtError.code === "ai_provider_invalid_json" &&
    typeof caughtError.details?.response === "string"
  ) {
    const normalizedResponse = caughtError.details.response.trim();
    if (normalizedResponse.startsWith("<")) {
      return "AI 供应商返回了网页内容而不是接口 JSON，通常表示网关 URL、协议或鉴权配置不匹配。";
    }
    return "AI 供应商返回的内容不符合当前协议格式，通常表示网关 URL、模型协议或中转规则配置有误。";
  }

  if (
    caughtError.code === "ai_provider_http_error" &&
    caughtError.statusCode === 502 &&
    typeof caughtError.details?.response === "string"
  ) {
    try {
      const providerPayload = JSON.parse(caughtError.details.response);
      const providerMessage =
        providerPayload?.error?.message ??
        providerPayload?.message ??
        "";
      if (typeof providerMessage === "string" && providerMessage.trim()) {
        return `AI 供应商鉴权失败：${providerMessage.trim()}`;
      }
    } catch {
      // 供应商返回的响应不一定总是标准 JSON，解析失败时回退到通用提示。
    }
  }

  return caughtError.message || "AI 对话调用失败";
}

/**
 * 语音识别失败时返回更可读的提示语。
 */
function getSpeechErrorMessage(errorCode: string): string {
  if (errorCode === "not-allowed") {
    return "浏览器未授予麦克风权限，请先允许当前页面使用麦克风。";
  }
  if (errorCode === "no-speech") {
    return "没有识别到语音内容，请靠近麦克风后重试。";
  }
  if (errorCode === "audio-capture") {
    return "当前设备没有可用麦克风，请检查音频输入设备。";
  }
  if (errorCode === "network") {
    return "浏览器语音识别网络请求失败，请检查当前网络。";
  }
  return "语音识别失败，请稍后重试或改用手动输入。";
}

/**
 * 开始语音输入。
 * 识别结果会先回填到输入框，识别结束后自动把当前文本发送给 AI。
 */
function startVoiceInput(): void {
  const RecognitionConstructor = getSpeechRecognitionConstructor();
  if (!RecognitionConstructor) {
    ElMessage.warning("当前浏览器不支持语音识别，建议使用新版 Chrome 或 Edge。");
    return;
  }
  if (speechListening.value) {
    return;
  }

  resetSpeechState();
  speechBaseQuestion.value = question.value;

  const recognition = new RecognitionConstructor();
  recognition.lang = "zh-CN";
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    speechListening.value = true;
  };

  recognition.onresult = (event) => {
    let nextFinalText = speechFinalText.value;
    let nextInterimText = "";

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const transcript = result[0]?.transcript?.trim() ?? "";
      if (!transcript) {
        continue;
      }

      if (result.isFinal) {
        nextFinalText = mergeSpeechQuestion(nextFinalText, transcript);
      } else {
        nextInterimText = mergeSpeechQuestion(nextInterimText, transcript);
      }
    }

    speechFinalText.value = nextFinalText;
    speechInterimText.value = nextInterimText;
    question.value = mergeSpeechQuestion(
      speechBaseQuestion.value,
      mergeSpeechQuestion(nextFinalText, nextInterimText),
    );
  };

  recognition.onerror = (event) => {
    speechListening.value = false;
    speechRecognition.value = null;
    speechInterimText.value = "";
    ElMessage.warning(getSpeechErrorMessage(event.error));
  };

  recognition.onend = () => {
    speechListening.value = false;
    speechRecognition.value = null;

    const shouldAutoSend = Boolean(question.value.trim());
    resetSpeechState();

    if (shouldAutoSend) {
      void submitQuestion();
    }
  };

  speechRecognition.value = recognition;

  try {
    recognition.start();
  } catch (caughtError) {
    speechRecognition.value = null;
    speechListening.value = false;
    resetSpeechState();
    const message = caughtError instanceof Error ? caughtError.message : "启动语音识别失败";
    ElMessage.warning(message);
  }
}

/**
 * 提交当前问题到后端 AI 对话接口。
 * 这里会把当前对话历史一并带上，使后端能在同一条记录上下文里连续回答。
 */
async function submitQuestion(): Promise<void> {
  if (!props.record) {
    return;
  }

  if (!canUseAiAnalysis.value) {
    ElMessage.warning("当前账号尚未开通 AI 分析权限。");
    return;
  }

  if (runtimeModels.value.length > 0 && selectedModelId.value === null) {
    ElMessage.warning("请选择一个已启用的 AI 模型配置后再发起对话。");
    return;
  }

  const normalizedQuestion = question.value.trim();
  if (!normalizedQuestion) {
    return;
  }

  chatErrorMessage.value = "";
  abortActiveChatStream();

  const nextMessages: AIChatMessage[] = [
    ...messages.value,
    createChatMessage("user", normalizedQuestion),
  ];
  const assistantMessage = createChatMessage("assistant", "");

  messages.value = [
    ...nextMessages,
    assistantMessage,
  ];
  question.value = "";
  sending.value = true;
  streamingAssistantMessageId.value = assistantMessage.localId;
  const abortController = new AbortController();
  activeChatAbortController.value = abortController;

  try {
    await streamAiChat(props.record.id, {
      question: normalizedQuestion,
      model_profile_id: selectedModelId.value,
      provider_hint: activeRuntimeModel.value?.displayName ?? null,
      history: nextMessages.map((item) => ({
        role: item.role,
        content: item.content,
      })),
    }, {
      onMeta: (responseDto) => {
        const response = mapAIChatResponseDto(responseDto);
        referencedFiles.value = response.referencedFiles;
        suggestedQuestions.value = response.suggestedQuestions;
      },
      onDelta: (deltaText) => {
        if (!deltaText) {
          return;
        }

        messages.value = messages.value.map((item) =>
          item.role === "assistant" && item.localId === assistantMessage.localId
            ? {
                ...item,
                content: `${item.content}${deltaText}`,
              }
            : item,
        );
      },
      onDone: (responseDto) => {
        const response = mapAIChatResponseDto(responseDto);
        referencedFiles.value = response.referencedFiles;
        suggestedQuestions.value = response.suggestedQuestions;
        messages.value = messages.value.map((item) =>
          item.role === "assistant" && item.localId === assistantMessage.localId
            ? {
                ...item,
                content: response.answer,
              }
            : item,
        );
      },
    }, abortController.signal);
  } catch (caughtError) {
    if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
      return;
    }

    const errorMessage = getAiChatRequestErrorMessage(caughtError);
    chatErrorMessage.value = errorMessage;
    messages.value = [
      ...nextMessages,
      createChatMessage(
        "assistant",
        "当前这轮 AI 对话没有成功返回。你可以稍后重试，或继续使用人工复核表单完成当前记录的判断。",
      ),
    ];
  } finally {
    if (activeChatAbortController.value === abortController) {
      activeChatAbortController.value = null;
    }
    streamingAssistantMessageId.value = null;
    sending.value = false;
  }
}

watch(
  () => selectedModelId.value,
  (nextModelId) => {
    if (runtimeModels.value.length === 0) {
      return;
    }

    setStoredPreferredRuntimeModelId(nextModelId);
  },
);

watch(
  () => [props.modelValue, props.record?.id],
  async ([visible]) => {
    if (visible) {
      resetDialogState();
      await loadRuntimeModels();
      return;
    }
    abortActiveChatStream();
    cleanupVoiceInput();
  },
  { immediate: true },
);

watch(
  () => previewFiles.value,
  (nextFiles) => {
    if (nextFiles.length === 0) {
      activePreviewFileId.value = null;
      return;
    }

    if (!nextFiles.some((file) => file.id === activePreviewFileId.value)) {
      activePreviewFileId.value = nextFiles[0].id;
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  abortActiveChatStream();
  cleanupVoiceInput();
});
</script>

<template>
  <AppDialog
    class="ai-chat-dialog"
    :model-value="modelValue"
    title="AI 对话分析"
    width="min(1320px, calc(100vw - 32px))"
    top="2vh"
    append-to-body
    destroy-on-close
    @close="closeDialog"
  >
    <div class="ai-chat__viewport">
      <div v-if="record" class="ai-chat">
        <section class="app-panel ai-chat__hero">
          <div class="ai-chat__hero-main">
            <strong>当前对话已绑定到这条检测记录</strong>
            <p class="muted-text">
              AI 会自动带入当前零件、设备、初检结果、最终结果、缺陷信息、文件对象和复核历史。后续你可以继续围绕这条记录多轮追问，而不是脱离上下文单独问。
            </p>

            <div class="ai-chat__model-picker">
              <ElSelect
                v-model="selectedModelId"
                placeholder="选择本轮对话模型"
                :loading="runtimeModelsLoading"
                :disabled="!canUseAiAnalysis"
              >
                <ElOption
                  v-for="item in runtimeModels"
                  :key="item.id"
                  :label="`${item.displayName} / ${item.gatewayName}`"
                  :value="item.id"
                />
              </ElSelect>
              <span class="muted-text">
                {{
                  canUseAiAnalysis
                    ? "这里只显示后端已启用且已配置密钥的模型。"
                    : "当前账号未开通 AI 分析权限，因此不会加载模型列表。"
                }}
              </span>
            </div>

            <ElAlert
              v-if="!canUseAiAnalysis"
              type="warning"
              show-icon
              :closable="false"
              title="当前账号未开通 AI 对话分析"
              description="你可以继续查看当前记录和图片证据，但无法直接向 AI 提问。请联系管理员在系统设置中开启该权限。"
              class="ai-chat__inline-alert"
            />

            <ElAlert
              v-if="runtimeModelsError"
              type="warning"
              show-icon
              :closable="false"
              title="运行时模型加载失败"
              :description="runtimeModelsError"
              class="ai-chat__inline-alert"
            />
          </div>
          <div class="ai-chat__hero-tags">
            <ElTag effect="dark" round>{{ record.recordNo }}</ElTag>
            <ElTag type="warning" effect="dark" round>{{ record.part.name }}</ElTag>
            <ElTag type="info" effect="dark" round>{{ record.device.deviceCode }}</ElTag>
            <ElTag
              v-if="activeRuntimeModel"
              type="success"
              effect="dark"
              round
            >
              {{ activeRuntimeModel.displayName }}
            </ElTag>
          </div>
        </section>

        <div class="ai-chat__layout">
          <section class="app-panel ai-chat__context">
            <div class="ai-chat__section-header">
              <div>
                <strong>记录上下文</strong>
                <p class="muted-text">左侧始终展示当前样本和图像对象，方便你边看边问。</p>
              </div>
            </div>

            <ElDescriptions :column="1" border>
              <ElDescriptionsItem label="零件">
                {{ record.part.name }} / {{ record.part.partCode }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="设备">
                {{ record.device.name }} / {{ record.device.deviceCode }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="MP 初检结果">
                {{ record.result }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="当前最终结果">
                {{ record.effectiveResult }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="缺陷类型">
                {{ record.defectType ?? "未记录" }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="置信度">
                {{ formatConfidence(record.confidenceScore) }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="拍摄时间">
                {{ formatDateTime(record.capturedAt) }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="检测完成">
                {{ formatDateTime(record.detectedAt) }}
              </ElDescriptionsItem>
            </ElDescriptions>

            <div class="ai-chat__preview">
              <div class="ai-chat__section-header">
                <div>
                  <strong>图像对象</strong>
                  <p class="muted-text">优先展示标注图，再展示源图和缩略图。</p>
                </div>
              </div>

              <div v-if="previewFiles.length > 0" class="ai-chat__preview-toolbar">
                <ElButton
                  v-for="file in previewFiles"
                  :key="file.id"
                  size="small"
                  :type="file.id === activePreviewFileId ? 'primary' : 'default'"
                  @click="activatePreviewFile(file.id)"
                >
                  {{ file.sequenceLabel }}
                </ElButton>
              </div>

              <div class="ai-chat__preview-stage">
                <template v-if="activePreviewFile">
                  <ElButton
                    v-if="hasMultiplePreviewFiles"
                    class="ai-chat__preview-nav ai-chat__preview-nav--prev"
                    :icon="ArrowLeft"
                    circle
                    aria-label="查看上一张图片"
                    @click="showPreviousPreviewFile"
                  />

                  <ElImage
                    v-if="activePreviewFile.previewUrl"
                    :src="activePreviewFile.previewUrl"
                    fit="contain"
                    class="ai-chat__preview-image"
                  >
                    <template #error>
                      <div class="ai-chat__preview-fallback">
                        <strong>{{ activePreviewFile.sequenceLabel }}</strong>
                        <p>当前对象已登记，但浏览器无法直接预览该文件。</p>
                        <code>{{ activePreviewFile.objectKey }}</code>
                      </div>
                    </template>
                  </ElImage>

                  <div v-else class="ai-chat__preview-fallback">
                    <strong>{{ activePreviewFile.sequenceLabel }}</strong>
                    <p>当前对象尚无可直接访问的预览地址，但 AI 对话仍会带上它的对象信息。</p>
                    <code>{{ activePreviewFile.objectKey }}</code>
                  </div>

                  <ElButton
                    v-if="hasMultiplePreviewFiles"
                    class="ai-chat__preview-nav ai-chat__preview-nav--next"
                    :icon="ArrowRight"
                    circle
                    aria-label="查看下一张图片"
                    @click="showNextPreviewFile"
                  />

                  <div v-if="hasMultiplePreviewFiles" class="ai-chat__preview-pagination">
                    <strong>{{ activePreviewFile.sequenceLabel }}</strong>
                    <span>{{ activePreviewPageText }}</span>
                  </div>
                </template>

                <div v-else class="ai-chat__preview-fallback">
                  <strong>暂无图像对象</strong>
                  <p>当前记录还没有登记源图、标注图或缩略图。</p>
                </div>
              </div>
            </div>
          </section>

          <section class="app-panel ai-chat__conversation">
            <div class="ai-chat__section-header">
              <div>
                <strong>多轮对话</strong>
                <p class="muted-text">问题会始终绑定在当前记录上下文里，适合连续追问。</p>
              </div>
            </div>

            <ElAlert
              v-if="chatErrorMessage"
              type="error"
              show-icon
              :closable="false"
              title="本轮 AI 对话失败"
              :description="chatErrorMessage"
              class="ai-chat__inline-alert"
            />

            <ElScrollbar class="ai-chat__messages">
              <div class="ai-chat__message-list">
                <article
                  v-for="(message, index) in messages"
                  :key="message.localId || `${message.role}-${index}-${message.createdAt}`"
                  class="ai-chat__message-row"
                >
                  <div
                    :class="[
                      'ai-chat__message',
                      message.role === 'assistant'
                        ? 'ai-chat__message--assistant'
                        : 'ai-chat__message--user',
                    ]"
                  >
                    <div class="ai-chat__message-meta">
                      <strong>{{ message.role === "assistant" ? "AI 助理" : "你" }}</strong>
                      <span>
                        {{
                          message.role === "assistant" &&
                          sending &&
                          message.localId === streamingAssistantMessageId
                            ? message.content
                              ? "流式输出中"
                              : "思考中"
                            : formatDateTime(message.createdAt)
                        }}
                      </span>
                    </div>
                    <div
                      v-if="
                        message.role === 'assistant' &&
                        sending &&
                        message.localId === streamingAssistantMessageId
                      "
                      class="ai-chat__thinking-indicator"
                      aria-label="AI 正在思考"
                    >
                      <span class="ai-chat__thinking-dot" />
                      <span class="ai-chat__thinking-dot" />
                      <span class="ai-chat__thinking-dot" />
                    </div>
                    <div class="ai-chat__message-content">{{ message.content }}</div>
                  </div>
                </article>
              </div>
            </ElScrollbar>

            <div v-if="referencedFiles.length > 0" class="ai-chat__reference-list">
              <span class="muted-text">本轮参考文件：</span>
              <ElTag
                v-for="file in referencedFiles"
                :key="`${file.fileKind}-${file.id}`"
                type="info"
                effect="dark"
                round
              >
                {{ getAiFileKindLabel(file.fileKind) }} / {{ file.objectKey }}
              </ElTag>
            </div>

            <div class="ai-chat__question-bank">
              <span class="muted-text">推荐追问</span>
              <div class="ai-chat__question-bank-actions">
                <ElButton
                  v-for="suggestedQuestion in suggestedQuestions"
                  :key="suggestedQuestion"
                  size="small"
                  plain
                  round
                  @click="useSuggestedQuestion(suggestedQuestion)"
                >
                  {{ suggestedQuestion }}
                </ElButton>
              </div>
            </div>

            <ElInput
              v-model="question"
              type="textarea"
              :rows="4"
              resize="none"
              placeholder="直接问当前零件的问题，例如：结合当前图片和结果，为什么建议人工复核？"
              @keydown.ctrl.enter.prevent="submitQuestion"
            />

            <div class="ai-chat__submit-bar">
              <div class="ai-chat__submit-meta">
                <span class="muted-text">按 Ctrl + Enter 发送，也可以直接语音提问。</span>
                <span v-if="speechInterimText" class="muted-text">
                  识别中：{{ speechInterimText }}
                </span>
                <span v-else-if="speechListening" class="muted-text">正在听你说话，识别结束后会自动发送。</span>
                <span
                  v-else-if="!speechRecognitionSupported"
                  class="muted-text"
                >
                  当前浏览器不支持语音识别，建议使用新版 Chrome 或 Edge。
                </span>
              </div>
              <div class="ai-chat__submit-actions">
                <ElButton
                  plain
                  :type="speechListening ? 'danger' : 'primary'"
                  :disabled="sending || !speechRecognitionSupported || !canUseAiAnalysis"
                  @click="speechListening ? stopVoiceInput() : startVoiceInput()"
                >
                  {{ speechListening ? "停止语音" : "语音提问并发送" }}
                </ElButton>
                <ElButton
                  type="primary"
                  :loading="sending"
                  :disabled="!question.trim() || !canUseAiAnalysis"
                  @click="submitQuestion"
                >
                  发送问题
                </ElButton>
              </div>
            </div>
          </section>
        </div>
      </div>

      <section v-else class="app-panel ai-chat__empty">
        <strong>当前没有可用的检测记录上下文</strong>
        <p class="muted-text">请先返回详情页加载一条记录，再打开 AI 对话分析。</p>
      </section>
    </div>
  </AppDialog>
</template>

<style scoped>
.ai-chat__viewport {
  max-height: calc(100vh - 150px);
  overflow-y: auto;
  padding-right: 6px;
}

.ai-chat {
  display: grid;
  gap: 18px;
}

.ai-chat__hero-main,
.ai-chat__context,
.ai-chat__conversation,
.ai-chat__empty {
  padding: 20px;
}

.ai-chat__hero-main,
.ai-chat__model-picker {
  display: grid;
  gap: 12px;
}

.ai-chat__model-picker,
.ai-chat__question-bank,
.ai-chat__question-bank-actions,
.ai-chat__submit-meta {
  min-width: 0;
}

.ai-chat__hero,
.ai-chat__section-header,
.ai-chat__submit-bar,
.ai-chat__submit-actions,
.ai-chat__hero-tags,
.ai-chat__preview-toolbar,
.ai-chat__reference-list {
  display: flex;
  gap: 12px;
}

.ai-chat__hero,
.ai-chat__section-header,
.ai-chat__submit-bar {
  justify-content: space-between;
  align-items: flex-start;
}

.ai-chat__hero-tags,
.ai-chat__preview-toolbar,
.ai-chat__reference-list {
  flex-wrap: wrap;
}

.ai-chat__question-bank {
  display: grid;
  gap: 10px;
}

.ai-chat__question-bank-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ai-chat__hero p,
.ai-chat__section-header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.ai-chat__layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.3fr);
  gap: 18px;
  align-items: start;
}

.ai-chat__context,
.ai-chat__conversation {
  display: grid;
  gap: 18px;
}

.ai-chat__inline-alert {
  margin-top: 2px;
}

.ai-chat__submit-meta {
  display: grid;
  gap: 6px;
}

.ai-chat__preview {
  display: grid;
  gap: 14px;
}

.ai-chat__preview-stage {
  position: relative;
  display: grid;
  min-height: 280px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.02);
}

.ai-chat__preview-image {
  width: 100%;
  height: 320px;
}

.ai-chat__preview-nav {
  position: absolute;
  top: 50%;
  z-index: 2;
  transform: translateY(-50%);
  border: 1px solid rgba(149, 184, 223, 0.18);
  background: rgba(10, 18, 30, 0.78);
  color: var(--app-text);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.26);
}

.ai-chat__preview-nav--prev {
  left: 14px;
}

.ai-chat__preview-nav--next {
  right: 14px;
}

.ai-chat__preview-pagination {
  position: absolute;
  left: 50%;
  bottom: 14px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border: 1px solid rgba(149, 184, 223, 0.16);
  border-radius: 999px;
  background: rgba(10, 18, 30, 0.8);
  color: var(--app-text);
  transform: translateX(-50%);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(10px);
}

.ai-chat__preview-fallback {
  min-height: 280px;
  display: grid;
  place-content: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
  color: var(--app-text-secondary);
}

.ai-chat__preview-fallback code {
  max-width: 100%;
  white-space: normal;
  word-break: break-all;
  color: var(--app-text);
}

.ai-chat__messages {
  height: clamp(320px, 42vh, 480px);
  padding-right: 6px;
}

.ai-chat__message-list {
  display: grid;
  gap: 14px;
}

.ai-chat__message-row {
  display: flex;
}

.ai-chat__message {
  max-width: 88%;
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
}

.ai-chat__message--assistant {
  background: rgba(255, 255, 255, 0.03);
}

.ai-chat__message--thinking {
  min-width: min(420px, 100%);
}

.ai-chat__message--user {
  margin-left: auto;
  background: rgba(47, 182, 162, 0.12);
  border-color: rgba(47, 182, 162, 0.22);
}

.ai-chat__message-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--app-text-secondary);
}

.ai-chat__message-content {
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--app-text);
}

.ai-chat__thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-chat__thinking-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(127, 228, 208, 0.9);
  animation: ai-chat-thinking 1.2s infinite ease-in-out;
}

.ai-chat__thinking-dot:nth-child(2) {
  animation-delay: 0.18s;
}

.ai-chat__thinking-dot:nth-child(3) {
  animation-delay: 0.36s;
}

.ai-chat__reference-list {
  align-items: center;
}

.ai-chat__submit-bar {
  gap: 16px;
  padding-top: 4px;
  border-top: 1px solid rgba(149, 184, 223, 0.12);
}

.ai-chat__submit-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

:deep(.ai-chat__question-bank-actions .el-button) {
  margin-left: 0;
}

:deep(.ai-chat__reference-list .el-tag) {
  max-width: 100%;
}

:deep(.ai-chat__reference-list .el-tag__content) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes ai-chat-thinking {
  0%,
  80%,
  100% {
    transform: scale(0.72);
    opacity: 0.45;
  }

  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 1320px) {
  .ai-chat__layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .ai-chat__viewport {
    max-height: calc(100vh - 120px);
  }

  .ai-chat__hero,
  .ai-chat__section-header,
  .ai-chat__submit-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .ai-chat__message {
    max-width: 100%;
  }

  .ai-chat__preview-nav--prev {
    left: 10px;
  }

  .ai-chat__preview-nav--next {
    right: 10px;
  }

  .ai-chat__preview-pagination {
    bottom: 10px;
    padding: 7px 12px;
    gap: 8px;
    font-size: 12px;
  }
}

@media (max-height: 860px) {
  .ai-chat__viewport {
    max-height: calc(100vh - 110px);
  }

  .ai-chat__preview-image {
    height: 260px;
  }
}
</style>
