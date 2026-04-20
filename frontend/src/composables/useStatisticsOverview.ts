import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { fetchDevices } from "@/services/api/devices";
import { fetchParts } from "@/services/api/parts";
import {
  downloadStatisticsPdf,
  fetchStatisticsOverview,
  streamStatisticsAiAnalysis,
  type StatisticsOverviewQuery,
} from "@/services/api/statistics";
import { fetchRuntimeAIModels } from "@/services/api/settings";
import {
  mapAIRuntimeModelOptionDto,
  mapDeviceDto,
  mapPartDto,
  mapStatisticsAIAnalysisResponseDto,
  mapStatisticsOverviewDto,
} from "@/services/mappers/commonMappers";
import type {
  AIRuntimeModelOption,
  DeviceModel,
  PartModel,
  StatisticsAIAnalysisResponse,
  StatisticsOverview,
} from "@/types/models";
import { exportStatisticsReportPng } from "@/utils/statisticsReport";

const DEFAULT_DAYS = 14;

/**
 * 统计页组合式逻辑。
 * 统一管理筛选、概览加载、AI 分析和导出，避免页面脚本继续膨胀。
 */
export function useStatisticsOverview() {
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
   * 当前选中的运行时模型。
   */
  const activeRuntimeModel = computed<AIRuntimeModelOption | null>(() => {
    if (selectedModelId.value === null) {
      return null;
    }

    return runtimeModels.value.find((item) => item.id === selectedModelId.value) ?? null;
  });

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

    const [partsResult, devicesResult, runtimeModelsResult] = await Promise.allSettled([
      fetchParts({ limit: 200 }),
      fetchDevices({ limit: 200 }),
      fetchRuntimeAIModels(),
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
      if (!runtimeModels.value.some((item) => item.id === selectedModelId.value)) {
        selectedModelId.value = runtimeModels.value[0]?.id ?? null;
      }
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
      aiAnalysis.value = null;
      aiError.value = "";
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

    abortAiAnalysisStream();
    aiLoading.value = true;
    aiError.value = "";
    const abortController = new AbortController();
    activeAiStreamAbortController.value = abortController;

    try {
      const [startDate, endDate] = dateRange.value.length === 2 ? dateRange.value : [null, null];
      await streamStatisticsAiAnalysis({
        model_profile_id: selectedModelId.value,
        provider_hint: activeRuntimeModel.value?.displayName ?? null,
        note: analysisNote.value.trim() || null,
        start_date: startDate,
        end_date: endDate,
        days: days.value,
        part_id: selectedPartId.value,
        device_id: selectedDeviceId.value,
      }, {
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
        },
        onDone: (responseDto) => {
          aiAnalysis.value = mapStatisticsAIAnalysisResponseDto(responseDto);
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
      aiLoading.value = false;
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
  }

  /**
   * 导出当前统计视图为 PNG 图片。
   */
  async function exportPng(): Promise<void> {
    if (!overview.value) {
      ElMessage.warning("当前没有可导出的统计数据。");
      return;
    }

    await exportStatisticsReportPng({
      overview: overview.value,
      aiAnalysis: aiAnalysis.value,
      partLabel: selectedPartLabel.value,
      deviceLabel: selectedDeviceLabel.value,
    });
  }

  /**
   * 调用后端服务端导出接口下载 PDF。
   */
  function exportPdf(): void {
    if (!overview.value) {
      ElMessage.warning("当前没有可导出的统计数据。");
      return;
    }

    pdfExporting.value = true;
    const [startDate, endDate] = dateRange.value.length === 2 ? dateRange.value : [null, null];
    void downloadStatisticsPdf({
      model_profile_id: selectedModelId.value,
      provider_hint: activeRuntimeModel.value?.displayName ?? null,
      note: analysisNote.value.trim() || null,
      start_date: startDate,
      end_date: endDate,
      days: days.value,
      part_id: selectedPartId.value,
      device_id: selectedDeviceId.value,
      include_ai_analysis: true,
      include_sample_images: true,
      sample_image_limit: 4,
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
    error,
    aiError,
    referenceError,
    runtimeModels,
    partOptions,
    deviceOptions,
    selectedModelId,
    analysisNote,
    activeRuntimeModel,
    selectedPartLabel,
    selectedDeviceLabel,
    refresh,
    applyQuickDays,
    resetFilters,
    runAiAnalysis,
    exportPng,
    exportPdf,
  };
}
