<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import { detectionResultOptions, reviewStatusOptions } from "@/constants/options";
import { useRecordsList } from "@/composables/useRecordsList";
import RecordCreateDialog from "@/features/records/RecordCreateDialog.vue";
import { fetchDevices } from "@/services/api/devices";
import { fetchParts } from "@/services/api/parts";
import { createRecord } from "@/services/api/records";
import { mapDeviceDto, mapPartDto } from "@/services/mappers/commonMappers";
import type { DetectionRecordCreateRequestDto } from "@/types/api";
import type { DeviceModel, PartModel } from "@/types/models";
import { formatConfidence, formatDateTime } from "@/utils/format";

const router = useRouter();
const {
  loading,
  error,
  items,
  total,
  pageSize,
  currentPage,
  filters,
  handlePageChange,
  refresh,
  applyFilters,
  resetFilters,
} = useRecordsList();

const optionsLoading = ref(false);
const creating = ref(false);
const dialogVisible = ref(false);
const parts = ref<PartModel[]>([]);
const devices = ref<DeviceModel[]>([]);

/**
 * 仅展示启用零件，避免录入到已下线的比赛工件定义。
 */
const activeParts = computed(() => parts.value.filter((item) => item.isActive));

/**
 * 疑似样本提示文案。
 */
const uncertainCount = computed(() => items.value.filter((item) => item.result === "uncertain").length);

/**
 * 拉取创建记录与筛选下拉所需的零件、设备选项。
 */
async function loadOptions(): Promise<void> {
  optionsLoading.value = true;

  try {
    const [partResponse, deviceResponse] = await Promise.all([
      fetchParts({
        limit: 100,
      }),
      fetchDevices({
        limit: 100,
      }),
    ]);
    parts.value = partResponse.items.map(mapPartDto);
    devices.value = deviceResponse.items.map(mapDeviceDto);
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "筛选选项加载失败";
    ElMessage.error(message);
  } finally {
    optionsLoading.value = false;
  }
}

/**
 * 打开检测详情。
 */
function openRecordDetail(recordId: number): void {
  void router.push({
    name: "record-detail",
    params: {
      id: recordId,
    },
  });
}

/**
 * 打开新增记录弹窗。
 */
function openCreateDialog(): void {
  dialogVisible.value = true;
}

/**
 * 提交新增记录。
 */
async function handleCreateRecord(payload: DetectionRecordCreateRequestDto): Promise<void> {
  creating.value = true;

  try {
    const createdRecord = await createRecord(payload);
    dialogVisible.value = false;
    ElMessage.success("检测记录已创建，当前结果默认为 MP 初检结果");
    await refresh();
    openRecordDetail(createdRecord.id);
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "检测记录创建失败";
    ElMessage.error(message);
  } finally {
    creating.value = false;
  }
}

/**
 * 应用列表筛选。
 */
async function handleFilterSearch(): Promise<void> {
  await applyFilters();
}

/**
 * 清空列表筛选。
 */
async function handleFilterReset(): Promise<void> {
  await resetFilters();
}

onMounted(() => {
  void loadOptions();
});
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Records"
      title="检测记录"
      description="这里按检测事件管理流程：同一台设备可以上传多个零件类型的记录，只有疑似样本才进入详情页触发人工复核或云端大模型复核。"
    />

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      :title="error"
    />

    <section class="app-panel records-toolbar">
      <div class="toolbar-grid">
        <ElSelect v-model="filters.partId" clearable filterable placeholder="零件筛选" :loading="optionsLoading">
          <ElOption
            v-for="part in activeParts"
            :key="part.id"
            :label="`${part.name} / ${part.partCode}`"
            :value="part.id"
          />
        </ElSelect>
        <ElSelect v-model="filters.deviceId" clearable filterable placeholder="设备筛选" :loading="optionsLoading">
          <ElOption
            v-for="device in devices"
            :key="device.id"
            :label="`${device.name} / ${device.deviceCode}`"
            :value="device.id"
          />
        </ElSelect>
        <ElSelect v-model="filters.result" clearable placeholder="初检结果">
          <ElOption
            v-for="option in detectionResultOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </ElSelect>
        <ElSelect v-model="filters.reviewStatus" clearable placeholder="复核状态">
          <ElOption
            v-for="option in reviewStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </ElSelect>
      </div>

      <div class="records-toolbar__footer">
        <div class="records-toolbar__group">
          <ElTag round effect="plain">默认显示 MP 初检结果</ElTag>
          <ElTag round effect="plain">当前页疑似样本 {{ uncertainCount }} 条</ElTag>
          <ElTag round effect="plain">人工/大模型复核只在详情页触发</ElTag>
        </div>
        <div class="toolbar-actions">
          <ElButton @click="handleFilterReset">重置</ElButton>
          <ElButton @click="handleFilterSearch" :loading="loading">查询</ElButton>
          <ElButton @click="refresh" :loading="loading">刷新记录</ElButton>
          <ElButton type="primary" @click="openCreateDialog">新增检测记录</ElButton>
        </div>
      </div>
    </section>

    <section class="app-panel records-table">
      <ElTable :data="items" v-loading="loading" empty-text="当前还没有检测记录">
        <ElTableColumn prop="recordNo" label="记录编号" min-width="170" />
        <ElTableColumn label="零件" min-width="180">
          <template #default="{ row }">
            {{ row.part.name }} / {{ row.part.partCode }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="设备" min-width="180">
          <template #default="{ row }">
            {{ row.device.name }} / {{ row.device.deviceCode }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="MP 初检" min-width="110">
          <template #default="{ row }">
            <StatusTag :value="row.result" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="最终结果" min-width="110">
          <template #default="{ row }">
            <StatusTag :value="row.effectiveResult" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="复核状态" min-width="110">
          <template #default="{ row }">
            <StatusTag :value="row.reviewStatus" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="置信度" min-width="100">
          <template #default="{ row }">
            {{ formatConfidence(row.confidenceScore) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="拍摄时间" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.capturedAt) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <ElButton text type="primary" @click="openRecordDetail(row.id)">
              {{ row.reviewStatus === "pending" ? "进入复核" : "查看详情" }}
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>

      <div class="records-table__footer">
        <ElPagination
          background
          layout="prev, pager, next, total"
          :page-size="pageSize"
          :total="total"
          :current-page="currentPage"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <RecordCreateDialog
      v-model="dialogVisible"
      :parts="activeParts"
      :devices="devices"
      :submitting="creating"
      @submit="handleCreateRecord"
    />
  </div>
</template>

<style scoped>
.records-toolbar,
.records-table {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.records-toolbar__footer,
.records-table__footer,
.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.records-toolbar__group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 1200px) {
  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .records-toolbar__footer,
  .records-table__footer,
  .toolbar-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
