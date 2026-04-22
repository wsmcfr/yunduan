import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { fetchDevices } from "@/services/api/devices";
import { fetchParts } from "@/services/api/parts";
import {
  downloadStatisticsPdf,
  fetchStatisticsOverview,
  streamStatisticsAiChat,
  streamStatisticsAiAnalysis,
  type StatisticsOverviewQuery,
} from "@/services/api/statistics";
import { fetchRuntimeAIModels } from "@/services/api/settings";
import {
  mapStatisticsAIChatResponseDto,
  mapAIRuntimeModelOptionDto,
  mapDeviceDto,
  mapPartDto,
  mapStatisticsAIAnalysisResponseDto,
  mapStatisticsOverviewDto,
} from "@/services/mappers/commonMappers";
import { useAuthStore } from "@/stores/auth";
import type {
  AIChatMessage,
  AIRuntimeModelOption,
  DeviceModel,
  PartModel,
  StatisticsAIAnalysisResponse,
  StatisticsAIChatResponse,
  StatisticsOverview,
} from "@/types/models";
import type {
  StatisticsExportConversationMessageDto,
  StatisticsPdfExportMode,
} from "@/types/api";
import {
  getStoredPreferredRuntimeModelId,
  resolvePreferredRuntimeModelId,
  setStoredPreferredRuntimeModelId,
} from "@/utils/aiModelSelection";
import {
  AI_CHAT_QUESTION_MAX_CHARACTERS,
  buildAiChatHistoryPayload,
} from "@/utils/aiChatHistory";
import { exportStatisticsReportPng } from "@/utils/statisticsReport";

const DEFAULT_DAYS = 14;
const VISUAL_EXPORT_SAMPLE_IMAGE_LIMIT = 4;
const LIGHTWEIGHT_EXPORT_SAMPLE_IMAGE_LIMIT = 2;

/**
 * 统计页组合式逻辑。
 * 统一管理筛选、概览加载、AI 分析和导出，避免页面脚本继续膨胀。
 */
export function useStatisticsOverview() {
  const authStore = useAuthStore();

  /**
   * 当前筛选窗口的快捷天数。
   * 当用户改用自定义日期范围时，仍保留这个值作为后端窗口参数。
   */
  const days = ref(DEFAULT_DAYS);

  /**
   * 自定义日期范围。
   * 使用字符串数组是为了直接匹配 Element Plus `value-format` 的输出。
   */
  const dateRange = ref<string[]>([]);

  /**
   * 当前选中的零件与设备过滤条件。
   */
  const selectedPartId = ref<number | null>(null);
  const selectedDeviceId = ref<number | null>(null);

  /**
   * 统计概览、AI 分析与基础选项的加载状态。
   */
  const loading = ref(false);
  const aiLoading = ref(false);
  const referenceLoading = ref(false);
  const pdfExporting = ref(false);

  /**
   * 页面核心数据与错误信息。
   */
  const overview = ref<StatisticsOverview | null>(null);
  const aiAnalysis = ref<StatisticsAIAnalysisResponse | null>(null);
  const error = ref("");
  const aiError = ref("");
  const referenceError = ref("");
  const activeAiStreamAbortController = ref<AbortController | null>(null);

  /**
   * AI 模型、零件和设备选项。
   */
  const runtimeModels = ref<AIRuntimeModelOption[]>([]);
  const partOptions = ref<PartModel[]>([]);
  const deviceOptions = ref<DeviceModel[]>([]);
  const selectedModelId = ref<number | null>(null);

  /**
   * 用户对统计 AI 分析的补充关注点。
   */
  const analysisNote = ref("");

  /**
   * 统计 AI 工作台中的追问输入、多轮消息和推荐追问。
   * 这里和单条复检页保持一致，统一用本地消息 ID 驱动流式更新。
   */
  const aiQuestion = ref("");
  const aiMessages = ref<AIChatMessage[]>([]);
  const aiSuggestedQuestions = ref<string[]>([]);
  const chatSending = ref(false);
  const streamingAssistantMessageId = ref<string | null>(null);

  /**
   * 当前选中的运行时模型。
   */
  const activeRuntimeModel = computed<AIRuntimeModelOption | null>(() => {
    if (selectedModelId.value === null) {
      return null;
    }

    return runtimeModels.value.find((item) => item.id === selectedModelId.value) ?? null;
  });

  /**
   * 当前账号是否已获管理员授权使用 AI 分析。
   * 统计页据此决定是否加载模型列表以及是否允许发起分析。
   */
  const canUseAiAnalysis = computed(() => authStore.currentUser?.canUseAiAnalysis ?? false);

  /**
   * 当前筛选到的零件和设备名称。
   * 导出报告时会把这些名称写入标题区，而不是只写编号。
   */
  const selectedPartLabel = computed(() => {
    const matchedPart = partOptions.value.find((item) => item.id === selectedPartId.value);
    return matchedPart ? `${matchedPart.name} / ${matchedPart.partCode}` : null;
  });

  const selectedDeviceLabel = computed(() => {
    const matchedDevice = deviceOptions.value.find((item) => item.id === selectedDeviceId.value);
    return matchedDevice ? `${matchedDevice.name} / ${matchedDevice.deviceCode}` : null;
  });

  /**
   * 当前统计 AI 工作台是否存在正在进行的流式请求。
   * 生成批次分析和继续追问共用同一条 SSE 中止控制器，因此这里统一收口。
   */
  const isAiStreaming = computed(() => aiLoading.value || chatSending.value);

  /**
   * 生成一条前端本地消息唯一 ID。
   * 统计页和单条复检页都依赖稳定主键来定位当前流式占位消息，不能再依赖时间戳碰撞概率。
   */
  function createLocalMessageId(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }

    return `stats-chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }

  /**
   * 统一创建统计 AI 工作台中的一条消息。
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
   * 基于当前统计概览生成一组默认推荐追问。
   * 当后端尚未返回更细的推荐问题时，前端先给出一组稳定入口，避免工作台出现空白。
   */
  function buildDefaultSuggestedQuestions(
    currentOverview: StatisticsOverview | null,
  ): string[] {
    const suggestions = [
      "当前批次最需要优先处理的风险点是什么？",
      "从现有统计看，更像设备问题还是零件批次问题？",
      "待审核数量会不会掩盖真实良率？",
      "接下来还需要补哪些数据，才能把结论说稳？",
    ];

    const topDefect = currentOverview?.defectDistribution[0];
    if (topDefect?.defectType) {
      suggestions.unshift(`围绕“${topDefect.defectType}”继续分析，当前最该先排查什么？`);
    }

    const topPart = currentOverview?.partQualityRanking[0];
    if (topPart?.partName) {
      suggestions.push(`${topPart.partName} 这类零件为什么会排到风险前列？`);
    }

    return suggestions.slice(0, 4);
  }

  /**
   * 切换筛选窗口或重新生成分析时，重置统计 AI 工作台状态。
   */
  function resetAiWorkspace(): void {
    aiAnalysis.value = null;
    aiQuestion.value = "";
    aiMessages.value = [];
    aiSuggestedQuestions.value = buildDefaultSuggestedQuestions(overview.value);
    aiError.value = "";
    streamingAssistantMessageId.value = null;
    aiLoading.value = false;
    chatSending.value = false;
  }

  /**
   * 把当前筛选窗口和模型选择统一转换成统计 AI 请求体公共部分。
   * 单次分析、继续追问和 PDF 导出都复用这套映射，避免字段口径漂移。
   */
  function buildAiScopePayload() {
    const [startDate, endDate] = dateRange.value.length === 2 ? dateRange.value : [null, null];
    return {
      model_profile_id: selectedModelId.value,
      provider_hint: activeRuntimeModel.value?.displayName ?? null,
      note: analysisNote.value.trim() || null,
      start_date: startDate,
      end_date: endDate,
      days: days.value,
      part_id: selectedPartId.value,
      device_id: selectedDeviceId.value,
    };
  }

  /**
   * 提取统计 AI 工作台里真正需要导出的多轮追问消息。
   * 主分析正文已经单独走 `cached_ai_answer`，这里从第一条用户消息开始截取，
   * 避免把“主分析 assistant 首条消息”在 PDF/图片里重复渲染两遍。
   */
  function resolveExportConversationMessages(): AIChatMessage[] {
    const firstUserMessageIndex = aiMessages.value.findIndex((item) => item.role === "user");
    if (firstUserMessageIndex < 0) {
      return [];
    }

    return aiMessages.value
      .slice(firstUserMessageIndex)
      .filter((item) => item.content.trim().length > 0);
  }

  /**
   * 生成页面上真正要展示的“多轮追问”消息。
   * 首轮批次分析会单独显示在分析正文区，因此这里从第一条用户提问开始展示，
   * 避免还没追问时，追问区就先出现一大段首轮分析正文。
   *
   * 与导出快照不同，这里保留空内容的助手占位消息，
   * 这样流式追问刚开始时仍然可以显示“思考中”的状态。
   */
  const visibleAiMessages = computed<AIChatMessage[]>(() => {
    const firstUserMessageIndex = aiMessages.value.findIndex((item) => item.role === "user");
    if (firstUserMessageIndex < 0) {
      return [];
    }

    return aiMessages.value.slice(firstUserMessageIndex);
  });

  /**
   * 把前端会话消息转换成后端 PDF 导出接口需要的 DTO 结构。
   * 导出链路只保留角色、正文和时间戳，避免把前端局部状态字段一并带到后端。
   */
  function buildExportConversationSnapshot(): StatisticsExportConversationMessageDto[] {
    return resolveExportConversationMessages().map((item) => ({
      role: item.role,
      content: item.content,
      created_at: item.createdAt,
    }));
  }

  /**
   * 兜底提取一条可复用的 AI 分析正文。
   * 如果用户没有先点“生成 AI 分析”，而是直接通过追问得到了一轮助手回答，
   * 导出 PDF 时也不应该出现“完全没有 AI 内容”的空白状态。
   */
  function resolveFallbackExportAiAnswer(): {
    answer: string | null;
    generatedAt: string | null;
  } {
    const firstAssistantMessage = resolveExportConversationMessages().find((item) =>
      item.role === "assistant" && item.content.trim().length > 0,
    );

    if (!firstAssistantMessage) {
      return {
        answer: null,
        generatedAt: null,
      };
    }

    return {
      answer: firstAssistantMessage.content,
      generatedAt: firstAssistantMessage.createdAt,
    };
  }

  /**
   * 只更新当前正在流式输出的那一条助手消息。
   * 这里必须用本地消息 ID 精确定位，避免文本串到用户问题气泡里。
   */
  function appendToAssistantMessage(messageId: string, deltaText: string): void {
    aiMessages.value = aiMessages.value.map((item) =>
      item.role === "assistant" && item.localId === messageId
        ? {
            ...item,
            content: `${item.content}${deltaText}`,
          }
        : item,
    );
  }

  /**
   * 用最终完成的文本覆盖当前助手占位消息。
   * 这样即便上游在 `done` 事件里做了收尾修正，前端也能同步成最终版本。
   */
  function replaceAssistantMessage(messageId: string, content: string): void {
    aiMessages.value = aiMessages.value.map((item) =>
      item.role === "assistant" && item.localId === messageId
        ? {
            ...item,
            content,
          }
        : item,
    );
  }

  /**
   * 把页面筛选条件转换成后端接口需要的查询参数。
   */
  function buildOverviewQuery(): StatisticsOverviewQuery {
    const [startDate, endDate] = dateRange.value.length === 2 ? dateRange.value : [null, null];
    return {
      startDate,
      endDate,
      days: days.value,
      partId: selectedPartId.value,
      deviceId: selectedDeviceId.value,
    };
  }

  /**
   * 加载页面依赖的零件、设备与运行时模型选项。
   * 这里使用 `allSettled`，避免某一类选项失败就把整个统计页阻塞住。
   */
  async function loadReferenceData(): Promise<void> {
    referenceLoading.value = true;
    referenceError.value = "";

    const runtimeModelRequest = canUseAiAnalysis.value
      ? fetchRuntimeAIModels()
      : Promise.resolve({ items: [] });

    const [partsResult, devicesResult, runtimeModelsResult] = await Promise.allSettled([
      /**
       * 后端主数据列表接口当前限制单次最大 `limit=100`。
       * 这里保持和后端契约一致，避免统计页初始化时因为 422 校验错误导致辅助选项加载失败。
       */
      fetchParts({ limit: 100 }),
      fetchDevices({ limit: 100 }),
      runtimeModelRequest,
    ]);

    const referenceErrors: string[] = [];

    if (partsResult.status === "fulfilled") {
      partOptions.value = partsResult.value.items.map(mapPartDto);
    } else {
      partOptions.value = [];
      referenceErrors.push("零件筛选项加载失败");
    }

    if (devicesResult.status === "fulfilled") {
      deviceOptions.value = devicesResult.value.items.map(mapDeviceDto);
    } else {
      deviceOptions.value = [];
      referenceErrors.push("设备筛选项加载失败");
    }

    if (runtimeModelsResult.status === "fulfilled") {
      runtimeModels.value = runtimeModelsResult.value.items.map(mapAIRuntimeModelOptionDto);
      selectedModelId.value = resolvePreferredRuntimeModelId(
        runtimeModels.value,
        getStoredPreferredRuntimeModelId(),
      );
      setStoredPreferredRuntimeModelId(selectedModelId.value);
    } else {
      runtimeModels.value = [];
      selectedModelId.value = null;
      referenceErrors.push("统计 AI 模型列表加载失败");
    }

    referenceError.value = referenceErrors.join("；");
    referenceLoading.value = false;
  }

  /**
   * 刷新统计概览。
   * 只要筛选窗口变化，就清空已有 AI 结果，避免用户误把旧分析当成新窗口结论。
   */
  async function refresh(): Promise<void> {
    abortAiAnalysisStream();
    loading.value = true;
    error.value = "";

    try {
      const overviewDto = await fetchStatisticsOverview(buildOverviewQuery());
      overview.value = mapStatisticsOverviewDto(overviewDto);
      resetAiWorkspace();
    } catch (caughtError) {
      error.value = caughtError instanceof Error ? caughtError.message : "统计概览加载失败";
    } finally {
      loading.value = false;
    }
  }

  /**
   * 应用快捷时间窗口，并立即刷新概览。
   */
  async function applyQuickDays(nextDays: number): Promise<void> {
    days.value = nextDays;
    dateRange.value = [];
    await refresh();
  }

  /**
   * 重置筛选条件并回到默认窗口。
   */
  async function resetFilters(): Promise<void> {
    abortAiAnalysisStream();
    days.value = DEFAULT_DAYS;
    dateRange.value = [];
    selectedPartId.value = null;
    selectedDeviceId.value = null;
    analysisNote.value = "";
    aiQuestion.value = "";
    await refresh();
  }

  /**
   * 基于当前统计窗口触发 AI 批次分析。
   */
  async function runAiAnalysis(): Promise<void> {
    if (!overview.value) {
      ElMessage.warning("请先加载统计概览，再发起 AI 分析。");
      return;
    }

    if (!canUseAiAnalysis.value) {
      ElMessage.warning("当前账号尚未开通 AI 分析权限。");
      return;
    }

    abortAiAnalysisStream();
    aiLoading.value = true;
    aiError.value = "";
    aiSuggestedQuestions.value = buildDefaultSuggestedQuestions(overview.value);
    const assistantMessage = createChatMessage("assistant", "");
    aiMessages.value = [assistantMessage];
    streamingAssistantMessageId.value = assistantMessage.localId;
    const abortController = new AbortController();
    activeAiStreamAbortController.value = abortController;

    try {
      await streamStatisticsAiAnalysis(buildAiScopePayload(), {
        onMeta: (responseDto) => {
          aiAnalysis.value = mapStatisticsAIAnalysisResponseDto(responseDto);
        },
        onDelta: (deltaText) => {
          if (!deltaText) {
            return;
          }

          if (!aiAnalysis.value) {
            aiAnalysis.value = {
              status: "streaming",
              answer: deltaText,
              providerHint: activeRuntimeModel.value?.displayName ?? null,
              generatedAt: new Date().toISOString(),
            };
            return;
          }

          aiAnalysis.value = {
            ...aiAnalysis.value,
            answer: `${aiAnalysis.value.answer}${deltaText}`,
          };
          appendToAssistantMessage(assistantMessage.localId, deltaText);
        },
        onDone: (responseDto) => {
          const response = mapStatisticsAIAnalysisResponseDto(responseDto);
          aiAnalysis.value = response;
          replaceAssistantMessage(assistantMessage.localId, response.answer);
        },
      }, abortController.signal);
    } catch (caughtError) {
      if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
        return;
      }

      aiError.value = caughtError instanceof Error ? caughtError.message : "统计 AI 分析失败";
      throw caughtError;
    } finally {
      if (activeAiStreamAbortController.value === abortController) {
        activeAiStreamAbortController.value = null;
      }
      if (streamingAssistantMessageId.value === assistantMessage.localId) {
        streamingAssistantMessageId.value = null;
      }
      aiLoading.value = false;
    }
  }

  /**
   * 将推荐追问一键回填到输入框，便于继续在当前统计窗口内深入追问。
   */
  function useSuggestedQuestion(question: string): void {
    aiQuestion.value = question;
  }

  /**
   * 在当前统计窗口上下文里继续追问 AI。
   * 这里会带上已存在的会话消息，使后端能把本轮问题放到同一批次的连续对话里理解。
   */
  async function submitAiQuestion(): Promise<void> {
    if (!overview.value) {
      ElMessage.warning("请先加载统计概览，再发起 AI 追问。");
      return;
    }

    if (!canUseAiAnalysis.value) {
      ElMessage.warning("当前账号尚未开通 AI 分析权限。");
      return;
    }

    const normalizedQuestion = aiQuestion.value.trim();
    if (!normalizedQuestion) {
      return;
    }

    /**
     * 单次追问正文需要先满足后端 schema 的长度约束。
     * 历史消息我们会自动裁剪，但当前问题属于用户当轮输入，超过上限时直接提示更清晰。
     */
    if (normalizedQuestion.length > AI_CHAT_QUESTION_MAX_CHARACTERS) {
      ElMessage.warning(
        `单次追问请控制在 ${AI_CHAT_QUESTION_MAX_CHARACTERS} 个字符以内，再重新发送。`,
      );
      return;
    }

    abortAiAnalysisStream();
    chatSending.value = true;
    aiError.value = "";
    const previousMessages = [...aiMessages.value];

    const nextMessages: AIChatMessage[] = [
      ...previousMessages,
      createChatMessage("user", normalizedQuestion),
    ];
    const assistantMessage = createChatMessage("assistant", "");
    aiMessages.value = [
      ...nextMessages,
      assistantMessage,
    ];
    aiQuestion.value = "";
    streamingAssistantMessageId.value = assistantMessage.localId;
    const abortController = new AbortController();
    activeAiStreamAbortController.value = abortController;

    try {
      await streamStatisticsAiChat({
        ...buildAiScopePayload(),
        question: normalizedQuestion,
        /**
         * 当前轮问题已经单独走 `question` 字段，不再重复塞进历史。
         * 历史上下文统一经过共享工具裁剪，避免长会话把后端 4000 字符约束打爆。
         */
        history: buildAiChatHistoryPayload(previousMessages),
      }, {
        onMeta: (responseDto) => {
          const response = mapStatisticsAIChatResponseDto(responseDto);
          aiSuggestedQuestions.value = response.suggestedQuestions;
        },
        onDelta: (deltaText) => {
          if (!deltaText) {
            return;
          }

          appendToAssistantMessage(assistantMessage.localId, deltaText);
        },
        onDone: (responseDto) => {
          const response: StatisticsAIChatResponse = mapStatisticsAIChatResponseDto(responseDto);
          aiSuggestedQuestions.value = response.suggestedQuestions;
          replaceAssistantMessage(assistantMessage.localId, response.answer);
        },
      }, abortController.signal);
    } catch (caughtError) {
      if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
        return;
      }

      aiError.value = caughtError instanceof Error ? caughtError.message : "统计 AI 追问失败";
      throw caughtError;
    } finally {
      if (activeAiStreamAbortController.value === abortController) {
        activeAiStreamAbortController.value = null;
      }
      if (streamingAssistantMessageId.value === assistantMessage.localId) {
        streamingAssistantMessageId.value = null;
      }
      chatSending.value = false;
    }
  }

  /**
   * 中止当前统计 AI 流。
   * 切换筛选窗口、离开页面或重新生成分析时都要停止旧流，避免把旧批次内容写进新窗口。
   */
  function abortAiAnalysisStream(): void {
    activeAiStreamAbortController.value?.abort();
    activeAiStreamAbortController.value = null;
    aiLoading.value = false;
    chatSending.value = false;
    streamingAssistantMessageId.value = null;
  }

  /**
   * 导出当前统计视图为 PNG 海报图。
   * 图片强调汇报展示效果，完整 AI 正文和追问留给 PDF 导出。
   */
  async function exportPng(): Promise<void> {
    if (!overview.value) {
      ElMessage.warning("当前没有可导出的统计数据。");
      return;
    }

    await exportStatisticsReportPng({
      overview: overview.value,
      aiAnalysis: aiAnalysis.value,
      aiConversation: resolveExportConversationMessages(),
      partLabel: selectedPartLabel.value,
      deviceLabel: selectedDeviceLabel.value,
    });
  }

  /**
   * 调用后端服务端导出接口下载 PDF。
   */
  function exportPdf(exportMode: StatisticsPdfExportMode): void {
    if (!overview.value) {
      ElMessage.warning("当前没有可导出的统计数据。");
      return;
    }

    pdfExporting.value = true;
    const [startDate, endDate] = dateRange.value.length === 2 ? dateRange.value : [null, null];
    const hasStableAiAnalysis = !aiLoading.value && Boolean(aiAnalysis.value?.answer.trim());
    const cachedAiConversation = buildExportConversationSnapshot();
    const fallbackAiSnapshot = resolveFallbackExportAiAnswer();
    /**
     * 导出 PDF 时，优先复用页面中已经存在的稳定分析结果；
     * 如果当前只有追问消息，也至少把第一条助手回复提升为导出摘要，避免 PDF 里完全看不到 AI 内容。
     */
    const cachedAiAnswer = hasStableAiAnalysis
      ? aiAnalysis.value?.answer ?? null
      : fallbackAiSnapshot.answer;
    const cachedAiGeneratedAt = hasStableAiAnalysis
      ? aiAnalysis.value?.generatedAt ?? null
      : fallbackAiSnapshot.generatedAt;
    const shouldIncludeAiSnapshot = canUseAiAnalysis.value
      && Boolean(cachedAiAnswer || cachedAiConversation.length > 0);
    /**
     * 两种 PDF 都要尽量带出统计页里的代表样本图。
     * 视觉版保留更多图片，轻量版则压缩数量，以换取更稳定的服务端导出耗时。
     */
    const includeSampleImages = overview.value.sampleGallery.totalImageCount > 0;
    const sampleImageLimit = includeSampleImages
      ? (exportMode === "visual"
          ? VISUAL_EXPORT_SAMPLE_IMAGE_LIMIT
          : LIGHTWEIGHT_EXPORT_SAMPLE_IMAGE_LIMIT)
      : 0;

    void downloadStatisticsPdf({
      export_mode: exportMode,
      model_profile_id: selectedModelId.value,
      provider_hint: activeRuntimeModel.value?.displayName ?? null,
      note: analysisNote.value.trim() || null,
      start_date: startDate,
      end_date: endDate,
      days: days.value,
      part_id: selectedPartId.value,
      device_id: selectedDeviceId.value,
      /**
       * PDF 导出优先复用页面上已经生成好的 AI 分析结果，
       * 避免导出动作再次发起一轮新的 AI 计算，把服务器 CPU 和等待时间一起拉高。
       */
      include_ai_analysis: shouldIncludeAiSnapshot,
      cached_ai_answer: cachedAiAnswer,
      cached_ai_provider_hint: hasStableAiAnalysis
        ? aiAnalysis.value?.providerHint ?? null
        : activeRuntimeModel.value?.displayName ?? null,
      cached_ai_generated_at: cachedAiGeneratedAt,
      cached_ai_conversation: cachedAiConversation,
      include_sample_images: includeSampleImages,
      sample_image_limit: sampleImageLimit,
    })
      .catch((caughtError) => {
        const message = caughtError instanceof Error ? caughtError.message : "服务端 PDF 导出失败";
        ElMessage.error(message);
      })
      .finally(() => {
        pdfExporting.value = false;
      });
  }

  /**
   * 页面初始化时同时拉取引用数据和统计概览。
   */
  async function initialize(): Promise<void> {
    await Promise.all([loadReferenceData(), refresh()]);
  }

  onMounted(() => {
    void initialize();
  });

  watch(
    () => selectedModelId.value,
    (nextModelId) => {
      if (runtimeModels.value.length === 0) {
        return;
      }

      setStoredPreferredRuntimeModelId(nextModelId);
    },
  );

  onBeforeUnmount(() => {
    abortAiAnalysisStream();
  });

  return {
    days,
    dateRange,
    selectedPartId,
    selectedDeviceId,
    loading,
    aiLoading,
    referenceLoading,
    pdfExporting,
    overview,
    aiAnalysis,
    aiQuestion,
    aiMessages,
    visibleAiMessages,
    aiSuggestedQuestions,
    error,
    aiError,
    referenceError,
    runtimeModels,
    partOptions,
    deviceOptions,
    selectedModelId,
    analysisNote,
    chatSending,
    streamingAssistantMessageId,
    activeRuntimeModel,
    canUseAiAnalysis,
    isAiStreaming,
    selectedPartLabel,
    selectedDeviceLabel,
    refresh,
    applyQuickDays,
    resetFilters,
    runAiAnalysis,
    useSuggestedQuestion,
    submitAiQuestion,
    exportPng,
    exportPdf,
  };
}
