<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import PartFormDialog from "@/features/parts/PartFormDialog.vue";
import {
  groupPartsByCategory,
  normalizePartCategoryLabel,
} from "@/features/parts/partCategories";
import { routeNames } from "@/router/routes";
import { createPart, fetchParts, updatePart } from "@/services/api/parts";
import { mapPartDto } from "@/services/mappers/commonMappers";
import type { PartCreateRequestDto, PartUpdateRequestDto } from "@/types/api";
import type { PartModel } from "@/types/models";
import { formatDateTime } from "@/utils/format";

type ActiveFilterValue = "all" | "true" | "false";

const ALL_CATEGORY_KEY = "all";

const loading = ref(false);
const saving = ref(false);
const error = ref("");
const items = ref<PartModel[]>([]);
const total = ref(0);
const pageSize = ref(10);
const currentPage = ref(1);
const keyword = ref("");
const activeFilter = ref<ActiveFilterValue>("all");
const dialogVisible = ref(false);
const editingPart = ref<PartModel | null>(null);
const activeCategoryKey = ref<string>(ALL_CATEGORY_KEY);
const router = useRouter();

/**
 * 当前页拿到的零件类型会先按分类聚合成入口卡片。
 * 主界面先看分类，再在下方查看该分类下的具体类型明细。
 */
const categoryEntries = computed(() => groupPartsByCategory(items.value));

/**
 * 当前选中的分类摘要。
 * 当处于“全部分类”模式时返回 null。
 */
const activeCategoryEntry = computed(() => {
  if (activeCategoryKey.value === ALL_CATEGORY_KEY) {
    return null;
  }

  return categoryEntries.value.find((item) => item.key === activeCategoryKey.value) ?? null;
});

/**
 * 表格明细区展示的零件类型列表。
 * 选中某个分类后，只保留该分类下的类型。
 */
const displayedParts = computed(() => activeCategoryEntry.value?.parts ?? items.value);

/**
 * 明细区标题根据当前分类入口自动切换。
 */
const detailTitle = computed(() => {
  if (!activeCategoryEntry.value) {
    return "全部零件类型明细";
  }
  return `${activeCategoryEntry.value.label} 分类明细`;
});

/**
 * 明细区说明文本。
 */
const detailDescription = computed(() => {
  if (!activeCategoryEntry.value) {
    return "先在上方选择分类入口，再查看该分类下的类型、来源设备和样本入口。";
  }

  return [
    `当前分类共 ${activeCategoryEntry.value.totalParts} 个类型`,
    `${activeCategoryEntry.value.recordCount} 条关联记录`,
    `${activeCategoryEntry.value.imageCount} 张关联图片`,
    activeCategoryEntry.value.latestSourceDevice
      ? `最近来源设备 ${activeCategoryEntry.value.latestSourceDevice.name} / ${activeCategoryEntry.value.latestSourceDevice.deviceCode}`
      : "最近来源设备待设备上报后自动识别",
  ].join(" · ");
});

/**
 * 当筛选变化导致分类入口集合改变时，自动回退到有效入口。
 * 这样不会出现分类卡片已经不存在，但下方明细还停在旧分类上的错位状态。
 */
watch(
  () => categoryEntries.value.map((item) => item.key).join("|"),
  () => {
    if (
      activeCategoryKey.value !== ALL_CATEGORY_KEY
      && !categoryEntries.value.some((item) => item.key === activeCategoryKey.value)
    ) {
      activeCategoryKey.value = ALL_CATEGORY_KEY;
    }
  },
  { immediate: true },
);

/**
 * 将界面上的启用状态筛选值转换成后端请求参数。
 */
function resolveActiveFilter(value: ActiveFilterValue): boolean | undefined {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return undefined;
}

/**
 * 拉取零件列表。
 */
async function loadParts(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    const response = await fetchParts({
      keyword: keyword.value.trim() || undefined,
      isActive: resolveActiveFilter(activeFilter.value),
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    });
    items.value = response.items.map(mapPartDto);
    total.value = response.total;
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "零件列表加载失败";
  } finally {
    loading.value = false;
  }
}

/**
 * 应用筛选条件，并将分页重置到第一页。
 */
async function handleSearch(): Promise<void> {
  currentPage.value = 1;
  activeCategoryKey.value = ALL_CATEGORY_KEY;
  await loadParts();
}

/**
 * 清空全部筛选条件。
 */
async function resetFilters(): Promise<void> {
  keyword.value = "";
  activeFilter.value = "all";
  currentPage.value = 1;
  activeCategoryKey.value = ALL_CATEGORY_KEY;
  await loadParts();
}

/**
 * 打开新增弹窗。
 */
function openCreateDialog(): void {
  editingPart.value = null;
  dialogVisible.value = true;
}

/**
 * 打开编辑弹窗。
 */
function openEditDialog(part: PartModel): void {
  editingPart.value = part;
  dialogVisible.value = true;
}

/**
 * 选中指定分类入口。
 */
function selectCategory(categoryKey: string): void {
  activeCategoryKey.value = categoryKey;
}

/**
 * 打开分类级图库。
 * 分类入口优先按 category 过滤，确保用户先看到同类零件的全部样本。
 */
function openCategoryGallery(categoryLabel: string): void {
  void router.push({
    name: routeNames.statisticsGallery,
    query: {
      days: "30",
      category: categoryLabel,
      part_category: categoryLabel,
    },
  });
}

/**
 * 进入当前零件类型对应的图库页。
 * 类型行入口会在分类范围内进一步锁定到具体 part_id。
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
 * 提交新增或编辑零件。
 */
async function handleSubmit(payload: PartCreateRequestDto | PartUpdateRequestDto): Promise<void> {
  saving.value = true;

  try {
    if (editingPart.value) {
      await updatePart(editingPart.value.id, payload as PartUpdateRequestDto);
      ElMessage.success("零件信息已更新");
    } else {
      await createPart(payload as PartCreateRequestDto);
      ElMessage.success("零件已创建");
    }
    dialogVisible.value = false;
    await loadParts();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "零件保存失败";
    ElMessage.error(message);
  } finally {
    saving.value = false;
  }
}

/**
 * 切换启用状态。
 * 工业主数据不做硬删除，只做启停，避免历史检测记录失去归属。
 */
async function togglePartStatus(part: PartModel): Promise<void> {
  try {
    await updatePart(part.id, {
      is_active: !part.isActive,
    });
    ElMessage.success(part.isActive ? "零件已停用" : "零件已启用");
    await loadParts();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "状态切换失败";
    ElMessage.error(message);
  }
}

/**
 * 将来源设备格式化成可读文本。
 */
function formatLatestSourceDevice(part: PartModel): string {
  if (!part.latestSourceDevice) {
    return "待设备上报";
  }

  return `${part.latestSourceDevice.name} / ${part.latestSourceDevice.deviceCode}`;
}

/**
 * 分页切换处理。
 */
async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page;
  await loadParts();
}

/**
 * 每页条数切换处理。
 * 主要流程：
 * 1. 更新零件列表的 page size；
 * 2. 清空当前分类入口选择并回到第一页；
 * 3. 重新读取后端数据，让分类卡片和明细表格来自同一批最新资源。
 *
 * @param nextPageSize Element Plus 分页组件传入的新每页条数。
 */
async function handlePageSizeChange(nextPageSize: number): Promise<void> {
  pageSize.value = nextPageSize;
  currentPage.value = 1;
  activeCategoryKey.value = ALL_CATEGORY_KEY;
  await loadParts();
}

onMounted(() => {
  void loadParts();
});
</script>

<template>
  <div class="page-grid parts-page">
    <PageHeader
      eyebrow="Parts"
      title="零件分类管理"
      description="这里先按零件分类组织入口，再查看分类下的具体类型。样本图片浏览、人工复检与 AI 复核统一走分类图库和检测详情页。"
    />

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      :title="error"
    />

    <section class="app-panel toolbar-panel">
      <div class="toolbar-grid">
        <ElInput
          v-model="keyword"
          clearable
          placeholder="按编码、名称、分类搜索"
          @keyup.enter="handleSearch"
        />
        <ElSelect v-model="activeFilter" placeholder="启用状态">
          <ElOption label="全部状态" value="all" />
          <ElOption label="仅启用" value="true" />
          <ElOption label="仅停用" value="false" />
        </ElSelect>
      </div>

      <div class="toolbar-actions">
        <ElButton @click="resetFilters">重置</ElButton>
        <ElButton @click="handleSearch" :loading="loading">查询</ElButton>
        <ElButton type="primary" @click="openCreateDialog">新增零件类型</ElButton>
      </div>
    </section>

    <section class="app-panel category-panel">
      <div class="category-panel__header">
        <div>
          <strong>分类入口</strong>
          <p class="muted-text">
            先看分类，再进入分类下的类型与样本。这样后续零件多起来时不会直接堆成一长页。
          </p>
        </div>
        <ElTag effect="dark" round type="info">
          当前页 {{ categoryEntries.length }} 个分类入口
        </ElTag>
      </div>

      <div class="category-rail">
        <button
          type="button"
          class="category-card"
          :class="{ 'category-card--active': activeCategoryKey === ALL_CATEGORY_KEY }"
          @click="selectCategory(ALL_CATEGORY_KEY)"
        >
          <strong>全部分类</strong>
          <span>{{ total }} 个类型</span>
          <span>查看当前筛选下的全部零件类型</span>
        </button>

        <button
          v-for="entry in categoryEntries"
          :key="entry.key"
          type="button"
          class="category-card"
          :class="{ 'category-card--active': activeCategoryKey === entry.key }"
          @click="selectCategory(entry.key)"
        >
          <strong>{{ entry.label }}</strong>
          <span>{{ entry.totalParts }} 个类型 · {{ entry.recordCount }} 条记录</span>
          <span>{{ entry.imageCount }} 张图片 · 最近上传 {{ formatDateTime(entry.latestUploadedAt) }}</span>
          <span v-if="entry.latestSourceDevice">
            最近来源 {{ entry.latestSourceDevice.name }} / {{ entry.latestSourceDevice.deviceCode }}
          </span>
        </button>
      </div>
    </section>

    <section class="app-panel table-section">
      <div class="table-section__header">
        <div>
          <strong>{{ detailTitle }}</strong>
          <p class="table-section__meta">{{ detailDescription }}</p>
        </div>

        <div class="table-section__header-actions">
          <ElButton
            v-if="activeCategoryEntry"
            type="primary"
            plain
            @click="openCategoryGallery(activeCategoryEntry.label)"
          >
            查看该分类图库
          </ElButton>
          <ElTag effect="dark" round type="success">
            当前显示 {{ displayedParts.length }} 个类型
          </ElTag>
        </div>
      </div>

      <ElTable :data="displayedParts" v-loading="loading" empty-text="暂无零件数据">
        <ElTableColumn prop="partCode" label="类型编码" min-width="150" />
        <ElTableColumn prop="name" label="类型名称" min-width="170" />
        <ElTableColumn label="所属分类" min-width="140">
          <template #default="{ row }">
            {{ normalizePartCategoryLabel(row.category) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="最近来源设备" min-width="220">
          <template #default="{ row }">
            {{ formatLatestSourceDevice(row) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="关联设备数" min-width="120">
          <template #default="{ row }">
            {{ row.deviceCount }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="关联记录" min-width="110">
          <template #default="{ row }">
            {{ row.recordCount }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="关联图片" min-width="110">
          <template #default="{ row }">
            {{ row.imageCount }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="启用状态" min-width="100">
          <template #default="{ row }">
            <ElTag :type="row.isActive ? 'success' : 'info'" round effect="dark">
              {{ row.isActive ? "启用" : "停用" }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="最近图片上传" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.latestUploadedAt) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" min-width="260">
          <template #default="{ row }">
            <div class="table-actions">
              <ElButton text type="success" @click="openPartGallery(row)">
                查看该类型样本
              </ElButton>
              <ElButton text type="primary" @click="openEditDialog(row)">编辑</ElButton>
              <ElButton text @click="togglePartStatus(row)">
                {{ row.isActive ? "停用" : "启用" }}
              </ElButton>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>

      <div class="table-section__footer">
        <ElPagination
          background
          layout="sizes, prev, pager, next, total"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          :current-page="currentPage"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <PartFormDialog
      v-model="dialogVisible"
      :submitting="saving"
      :initial-value="editingPart"
      @submit="handleSubmit"
    />
  </div>
</template>

<style scoped>
.toolbar-panel,
.category-panel,
.table-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.parts-page {
  align-content: start;
}

.table-section {
  align-content: start;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(180px, 0.7fr);
  gap: 16px;
}

.toolbar-actions,
.table-actions,
.table-section__header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.category-panel__header,
.table-section__header,
.table-section__footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.category-panel__header p,
.table-section__header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.category-rail {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(240px, 280px);
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
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.13), transparent 42%),
    rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 138, 31, 0.14);
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
  border-color: rgba(255, 138, 31, 0.34);
}

.category-card--active {
  border-color: rgba(255, 138, 31, 0.58);
  box-shadow: 0 18px 38px rgba(4, 12, 22, 0.28);
}

.category-card span,
.table-section__meta {
  color: var(--app-text-secondary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-actions,
  .category-panel__header,
  .table-section__header,
  .table-section__header-actions,
  .table-section__footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
