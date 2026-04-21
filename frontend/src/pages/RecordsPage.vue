<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import { useRecordsList } from "@/composables/useRecordsList";
import { detectionResultOptions, reviewStatusOptions } from "@/constants/options";
import {
  groupPartsByCategory,
  normalizePartCategoryLabel,
} from "@/features/parts/partCategories";
import RecordCreateDialog from "@/features/records/RecordCreateDialog.vue";
import { routeNames } from "@/router/routes";
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
 * 仅展示启用零件，避免录入到已下线的工件定义。
 */
const activeParts = computed(() => parts.value.filter((item) => item.isActive));

/**
 * 检测记录页也先按零件分类生成入口卡片。
 * 入口来自主数据定义，因此即使分类下暂时没有当前页数据，入口结构也保持稳定。
 */
const categoryEntries = computed(() => groupPartsByCategory(activeParts.value));

/**
 * 当前已选中的分类摘要。
 */
const activeCategoryEntry = computed(() => {
  if (!filters.partCategory) {
    return null;
  }

  return categoryEntries.value.find((item) => item.label === filters.partCategory) ?? null;
});

/**
 * 当前选中的具体零件类型。
 */
const activePart = computed(() => {
  return activeParts.value.find((item) => item.id === filters.partId) ?? null;
});

/**
 * 疑似样本提示文案。
 */
const uncertainCount = computed(() => items.value.filter((item) => item.result === "uncertain").length);

/**
 * 当前记录列表区域的标题。
 */
const recordTableTitle = computed(() => {
  if (activePart.value) {
    return `${activePart.value.name} / ${activePart.value.partCode} 检测记录`;
  }
  if (activeCategoryEntry.value) {
    return `${activeCategoryEntry.value.label} 分类检测记录`;
  }
  return "全部分类检测记录";
});

/**
 * 记录列表区域说明。
 */
const recordTableDescription = computed(() => {
  if (activePart.value) {
    return `当前已进一步锁定到具体类型 ${activePart.value.name}，适合直接查看该类型的上传和复检情况。`;
  }
  if (activeCategoryEntry.value) {
    return `当前分类下共 ${activeCategoryEntry.value.totalParts} 个类型，点击单条记录即可进入人工复检或 AI 对话工作区。`;
  }
  return "先按分类筛选，再进入具体记录详情。一个设备可以持续上传多个零件分类的记录。";
});

/**
 * 拉取创建记录与筛选下拉所需的零件、设备选项。
 */
async function loadOptions(): Promise<void> {
  optionsLoading.value = true;

  try {
    const [partResponse, deviceResponse] = await Promise.all([
      fetchParts({
        /**
         * 零件列表接口当前单次上限为 100。
         * 这里如果继续请求 200，会被后端参数校验直接拦成 422，页面就会弹出“接口请求失败”。
         */
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
    name: routeNames.recordDetail,
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
 * 打开当前分类对应的图库入口。
 * 记录页负责按分类筛查，真正的图片浏览继续下沉到图库页。
 */
function openCategoryGallery(): void {
  if (!filters.partCategory) {
    return;
  }

  void router.push({
    name: routeNames.statisticsGallery,
    query: {
      days: "30",
      category: filters.partCategory,
      part_category: filters.partCategory,
    },
  });
}

/**
 * 打开当前类型对应的图库入口。
 */
function openPartGallery(part: PartModel): void {
  const categoryLabel = normalizePartCategoryLabel(part.category);

  void router.push({
    name: routeNames.statisticsGallery,
    query: {
      days: "30",
      category: categoryLabel,
      part_category: categoryLabel,
      part_id: String(part.id),
    },
  });
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
 * 点击分类入口后立即应用分类筛选。
 * 如果当前具体类型不在该分类下，则自动清空类型筛选，避免条件互相冲突。
 */
async function selectCategory(categoryLabel?: string): Promise<void> {
  filters.partCategory = categoryLabel ?? undefined;

  if (filters.partId !== undefined) {
    const matchedPart = activeParts.value.find((item) => item.id === filters.partId);
    const matchedCategory = matchedPart ? normalizePartCategoryLabel(matchedPart.category) : null;
    if (!categoryLabel || matchedCategory !== categoryLabel) {
      filters.partId = undefined;
    }
  }

  await applyFilters();
}

/**
 * 用户选择具体零件类型后，同步补齐所属分类，避免顶部分类入口与具体类型筛选出现错位。
 */
function syncCategoryFromPart(): void {
  if (filters.partId === undefined) {
    return;
  }

  const matchedPart = activeParts.value.find((item) => item.id === filters.partId);
  filters.partCategory = matchedPart ? normalizePartCategoryLabel(matchedPart.category) : undefined;
}

/**
 * 应用列表筛选。
 */
async function handleFilterSearch(): Promise<void> {
  syncCategoryFromPart();
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
      description="这里先按零件分类筛查，再进入分类下的具体记录。分类负责承接批量浏览，单条详情页负责人工复核和 AI 问答。"
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
        <ElSelect
          v-model="filters.partCategory"
          clearable
          filterable
          placeholder="零件分类"
          :loading="optionsLoading"
        >
          <ElOption
            v-for="entry in categoryEntries"
            :key="entry.key"
            :label="`${entry.label}（${entry.totalParts} 个类型）`"
            :value="entry.label"
          />
        </ElSelect>
        <ElSelect
          v-model="filters.partId"
          clearable
          filterable
          placeholder="零件类型"
          :loading="optionsLoading"
        >
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
          <ElTag round effect="plain">设备可上传多个零件分类</ElTag>
        </div>
        <div class="toolbar-actions">
          <ElButton @click="handleFilterReset">重置</ElButton>
          <ElButton @click="handleFilterSearch" :loading="loading">查询</ElButton>
          <ElButton @click="refresh" :loading="loading">刷新记录</ElButton>
          <ElButton type="primary" @click="openCreateDialog">新增检测记录</ElButton>
        </div>
      </div>
    </section>

    <section class="app-panel category-panel">
      <div class="category-panel__header">
        <div>
          <strong>分类入口</strong>
          <p class="muted-text">
            先选择分类，再看该分类下的记录。分类入口来自零件主数据，不再把所有记录直接平铺在首页。
          </p>
        </div>
        <ElTag effect="dark" round type="info">
          共 {{ categoryEntries.length }} 个分类入口
        </ElTag>
      </div>

      <div class="category-rail">
        <button
          type="button"
          class="category-card"
          :class="{ 'category-card--active': !filters.partCategory }"
          @click="selectCategory()"
        >
          <strong>全部分类</strong>
          <span>查看当前筛选下的全部记录</span>
        </button>

        <button
          v-for="entry in categoryEntries"
          :key="entry.key"
          type="button"
          class="category-card"
          :class="{ 'category-card--active': filters.partCategory === entry.label }"
          @click="selectCategory(entry.label)"
        >
          <strong>{{ entry.label }}</strong>
          <span>{{ entry.totalParts }} 个类型 · {{ entry.recordCount }} 条历史记录</span>
          <span>{{ entry.imageCount }} 张历史图片 · 最近上传 {{ formatDateTime(entry.latestUploadedAt) }}</span>
        </button>
      </div>
    </section>

    <section class="app-panel records-table">
      <div class="records-table__header">
        <div>
          <strong>{{ recordTableTitle }}</strong>
          <p class="muted-text">{{ recordTableDescription }}</p>
        </div>
        <div class="records-table__header-actions">
          <ElButton
            v-if="activeCategoryEntry"
            plain
            type="primary"
            @click="openCategoryGallery"
          >
            查看该分类图库
          </ElButton>
          <ElButton
            v-if="activePart"
            plain
            type="success"
            @click="openPartGallery(activePart)"
          >
            查看该类型样本
          </ElButton>
        </div>
      </div>

      <ElTable :data="items" v-loading="loading" empty-text="当前还没有检测记录">
        <ElTableColumn label="所属分类" min-width="140">
          <template #default="{ row }">
            {{ normalizePartCategoryLabel(row.part.category ?? null) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="零件类型" min-width="190">
          <template #default="{ row }">
            {{ row.part.name }} / {{ row.part.partCode }}
          </template>
        </ElTableColumn>
        <ElTableColumn prop="recordNo" label="记录编号" min-width="170" />
        <ElTableColumn label="来源设备" min-width="180">
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
        <ElTableColumn label="操作" min-width="140">
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
.category-panel,
.records-table {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
}

.records-toolbar__footer,
.records-table__footer,
.toolbar-actions,
.records-table__header,
.records-table__header-actions,
.category-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.records-toolbar__group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.category-panel__header p,
.records-table__header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.category-rail {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(240px, 300px);
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.category-card {
  display: grid;
  gap: 8px;
  padding: 18px;
  width: 100%;
  font: inherit;
  text-align: left;
  color: inherit;
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 42%),
    rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(127, 228, 208, 0.12);
  border-radius: 20px;
  appearance: none;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.category-card:hover {
  transform: translateY(-2px);
  border-color: rgba(127, 228, 208, 0.28);
}

.category-card--active {
  border-color: rgba(127, 228, 208, 0.54);
  box-shadow: 0 18px 38px rgba(4, 12, 22, 0.28);
}

.category-card span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

@media (max-width: 1400px) {
  .toolbar-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .records-toolbar__footer,
  .records-table__footer,
  .toolbar-actions,
  .records-table__header,
  .records-table__header-actions,
  .category-panel__header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
