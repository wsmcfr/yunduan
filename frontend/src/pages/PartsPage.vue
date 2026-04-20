<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import PartFormDialog from "@/features/parts/PartFormDialog.vue";
import { routeNames } from "@/router/routes";
import { createPart, fetchParts, updatePart } from "@/services/api/parts";
import { mapPartDto } from "@/services/mappers/commonMappers";
import type { PartCreateRequestDto, PartUpdateRequestDto } from "@/types/api";
import type { PartModel } from "@/types/models";
import { formatDateTime } from "@/utils/format";

type ActiveFilterValue = "all" | "true" | "false";

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
const router = useRouter();

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
  await loadParts();
}

/**
 * 清空全部筛选条件。
 */
async function resetFilters(): Promise<void> {
  keyword.value = "";
  activeFilter.value = "all";
  currentPage.value = 1;
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
 * 进入当前零件类型对应的图库页。
 * 主数据页不直接堆图片，而是跳转到独立图库页浏览和进入复检。
 */
function openPartGallery(part: PartModel): void {
  void router.push({
    name: routeNames.statisticsGallery,
    query: {
      days: "30",
      part_id: String(part.id),
      category: part.category ?? "",
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
 * 分页切换处理。
 */
async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page;
  await loadParts();
}

onMounted(() => {
  void loadParts();
});
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Parts"
      title="零件类型管理"
      description="这里维护的是零件类型/分类主数据，不是单条检测记录。样本图片浏览、人工复检与 AI 复核统一走图库页和检测详情页。"
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

    <section class="app-panel table-section">
      <div class="table-section__header">
        <strong>零件类型列表</strong>
        <span class="table-section__meta">共 {{ total }} 条，建议优先维护实际会被设备上传和检测的零件类型</span>
      </div>

      <ElTable :data="items" v-loading="loading" empty-text="暂无零件数据">
        <ElTableColumn prop="partCode" label="类型编码" min-width="150" />
        <ElTableColumn prop="name" label="类型名称" min-width="160" />
        <ElTableColumn prop="category" label="上层分类" min-width="140" />
        <ElTableColumn prop="description" label="说明" min-width="260" />
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
        <ElTableColumn label="更新时间" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.updatedAt) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="最近图片上传" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.latestUploadedAt) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <ElButton text type="success" @click="openPartGallery(row)">
                查看图库
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
          layout="prev, pager, next, total"
          :page-size="pageSize"
          :total="total"
          :current-page="currentPage"
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
.table-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(180px, 0.7fr);
  gap: 16px;
}

.toolbar-actions,
.table-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-section__header,
.table-section__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.table-section__meta {
  color: var(--app-text-secondary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-actions,
  .table-section__header,
  .table-section__footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
