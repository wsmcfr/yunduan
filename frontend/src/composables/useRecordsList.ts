import { onMounted, reactive, ref } from "vue";

import { fetchRecords } from "@/services/api/records";
import { mapDetectionRecordDto } from "@/services/mappers/commonMappers";
import type { DetectionResult, ReviewStatus } from "@/types/api";
import type { DetectionRecordModel } from "@/types/models";

export interface RecordsFilters {
  partId: number | undefined;
  deviceId: number | undefined;
  result: DetectionResult | undefined;
  reviewStatus: ReviewStatus | undefined;
}

/**
 * 创建记录列表默认筛选条件。
 */
function createDefaultFilters(): RecordsFilters {
  return {
    partId: undefined,
    deviceId: undefined,
    result: undefined,
    reviewStatus: undefined,
  };
}

/**
 * 检测记录列表组合式逻辑。
 * 负责分页、筛选、加载和错误态管理，页面只消费整理后的状态。
 */
export function useRecordsList() {
  const loading = ref(false);
  const error = ref("");
  const items = ref<DetectionRecordModel[]>([]);
  const total = ref(0);
  const pageSize = ref(10);
  const currentPage = ref(1);
  const filters = reactive<RecordsFilters>(createDefaultFilters());

  /**
   * 重新拉取记录列表。
   * 查询参数统一从本组合式的分页和筛选状态生成。
   */
  async function refresh(): Promise<void> {
    loading.value = true;
    error.value = "";

    try {
      const response = await fetchRecords({
        partId: filters.partId,
        deviceId: filters.deviceId,
        result: filters.result,
        reviewStatus: filters.reviewStatus,
        skip: (currentPage.value - 1) * pageSize.value,
        limit: pageSize.value,
      });
      items.value = response.items.map(mapDetectionRecordDto);
      total.value = response.total;
    } catch (caughtError) {
      error.value = caughtError instanceof Error ? caughtError.message : "检测记录加载失败";
    } finally {
      loading.value = false;
    }
  }

  /**
   * 切换页码时刷新列表。
   */
  async function handlePageChange(page: number): Promise<void> {
    currentPage.value = page;
    await refresh();
  }

  /**
   * 应用筛选时回到第一页，避免当前页码超出新结果集范围。
   */
  async function applyFilters(): Promise<void> {
    currentPage.value = 1;
    await refresh();
  }

  /**
   * 清空全部筛选条件。
   */
  async function resetFilters(): Promise<void> {
    Object.assign(filters, createDefaultFilters());
    currentPage.value = 1;
    await refresh();
  }

  onMounted(() => {
    void refresh();
  });

  return {
    loading,
    error,
    items,
    total,
    pageSize,
    currentPage,
    filters,
    refresh,
    handlePageChange,
    applyFilters,
    resetFilters,
  };
}
