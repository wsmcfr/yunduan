<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import { deviceStatusOptions } from "@/constants/options";
import DeviceFormDialog from "@/features/devices/DeviceFormDialog.vue";
import { createDevice, fetchDevices, updateDevice } from "@/services/api/devices";
import { mapDeviceDto } from "@/services/mappers/commonMappers";
import type { DeviceCreateRequestDto, DeviceStatus, DeviceUpdateRequestDto } from "@/types/api";
import type { DeviceModel } from "@/types/models";
import { formatDateTime } from "@/utils/format";

const loading = ref(false);
const saving = ref(false);
const error = ref("");
const items = ref<DeviceModel[]>([]);
const total = ref(0);
const pageSize = ref(10);
const currentPage = ref(1);
const keyword = ref("");
const statusFilter = ref<DeviceStatus | undefined>(undefined);
const dialogVisible = ref(false);
const editingDevice = ref<DeviceModel | null>(null);

/**
 * 拉取设备列表。
 */
async function loadDevices(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    const response = await fetchDevices({
      keyword: keyword.value.trim() || undefined,
      status: statusFilter.value,
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    });
    items.value = response.items.map(mapDeviceDto);
    total.value = response.total;
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "设备列表加载失败";
  } finally {
    loading.value = false;
  }
}

/**
 * 应用设备筛选。
 */
async function handleSearch(): Promise<void> {
  currentPage.value = 1;
  await loadDevices();
}

/**
 * 清空设备筛选。
 */
async function resetFilters(): Promise<void> {
  keyword.value = "";
  statusFilter.value = undefined;
  currentPage.value = 1;
  await loadDevices();
}

/**
 * 打开新增设备弹窗。
 */
function openCreateDialog(): void {
  editingDevice.value = null;
  dialogVisible.value = true;
}

/**
 * 打开编辑设备弹窗。
 */
function openEditDialog(device: DeviceModel): void {
  editingDevice.value = device;
  dialogVisible.value = true;
}

/**
 * 提交设备表单。
 */
async function handleSubmit(payload: DeviceCreateRequestDto | DeviceUpdateRequestDto): Promise<void> {
  saving.value = true;

  try {
    if (editingDevice.value) {
      await updateDevice(editingDevice.value.id, payload as DeviceUpdateRequestDto);
      ElMessage.success("设备信息已更新");
    } else {
      await createDevice(payload as DeviceCreateRequestDto);
      ElMessage.success("设备已创建");
    }
    dialogVisible.value = false;
    await loadDevices();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "设备保存失败";
    ElMessage.error(message);
  } finally {
    saving.value = false;
  }
}

/**
 * 分页切换处理。
 */
async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page;
  await loadDevices();
}

onMounted(() => {
  void loadDevices();
});
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Devices"
      title="设备管理"
      description="设备页维护 MP157、F4、网关与其他节点的档案和在线状态。它只管理设备本身，不承担样本复核流程。"
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
          placeholder="按设备编码、名称或 IP 搜索"
          @keyup.enter="handleSearch"
        />
        <ElSelect v-model="statusFilter" clearable placeholder="设备状态">
          <ElOption
            v-for="option in deviceStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </ElSelect>
      </div>

      <div class="toolbar-actions">
        <ElButton @click="resetFilters">重置</ElButton>
        <ElButton @click="handleSearch" :loading="loading">查询</ElButton>
        <ElButton type="primary" @click="openCreateDialog">新增设备</ElButton>
      </div>
    </section>

    <section class="app-panel table-section">
      <div class="table-section__header">
        <strong>设备列表</strong>
        <span class="table-section__meta">共 {{ total }} 条，建议把主相机节点、F4 输送控制节点和网关节点分开建档</span>
      </div>

      <ElTable :data="items" v-loading="loading" empty-text="暂无设备数据">
        <ElTableColumn prop="deviceCode" label="设备编码" min-width="150" />
        <ElTableColumn prop="name" label="设备名称" min-width="160" />
        <ElTableColumn prop="deviceType" label="类型" min-width="120" />
        <ElTableColumn label="状态" min-width="100">
          <template #default="{ row }">
            <StatusTag :value="row.status" />
          </template>
        </ElTableColumn>
        <ElTableColumn prop="firmwareVersion" label="固件版本" min-width="130" />
        <ElTableColumn prop="ipAddress" label="IP 地址" min-width="150" />
        <ElTableColumn label="最近心跳" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.lastSeenAt) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <ElButton text type="primary" @click="openEditDialog(row)">编辑</ElButton>
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

    <DeviceFormDialog
      v-model="dialogVisible"
      :submitting="saving"
      :initial-value="editingDevice"
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
