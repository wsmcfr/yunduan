<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import AIGatewayFormDialog from "@/features/settings/AIGatewayFormDialog.vue";
import AIModelFormDialog from "@/features/settings/AIModelFormDialog.vue";
import {
  aiGatewayPresets,
  authModeLabels,
  gatewayVendorLabels,
  getModelTemplatesForGatewayVendor,
  modelVendorLabels,
  protocolLabels,
} from "@/features/settings/aiSettingsCatalog";
import {
  createAIGateway,
  createAIModel,
  deleteAIGateway,
  deleteAIModel,
  fetchAIGateways,
  updateAIGateway,
  updateAIModel,
} from "@/services/api/settings";
import { mapAIGatewayDto } from "@/services/mappers/commonMappers";
import { useAuthStore } from "@/stores/auth";
import type {
  AIGatewayCreateRequestDto,
  AIGatewayUpdateRequestDto,
  AIModelProfileCreateRequestDto,
  AIModelProfileUpdateRequestDto,
} from "@/types/api";
import type {
  AIDiscoveredModelCandidate,
  AIGatewayModel,
  AIModelProfile,
} from "@/types/models";
import { formatDateTime } from "@/utils/format";

const authStore = useAuthStore();
const loading = ref(false);
const gatewaySubmitting = ref(false);
const modelSubmitting = ref(false);
const error = ref("");
const gateways = ref<AIGatewayModel[]>([]);

const gatewayDialogVisible = ref(false);
const editingGateway = ref<AIGatewayModel | null>(null);
const activeGatewayPresetId = ref<string | null>(null);

const modelDialogVisible = ref(false);
const editingModel = ref<AIModelProfile | null>(null);
const activeModelTemplateId = ref<string | null>(null);
const activeModelGatewayId = ref<number | null>(null);

/**
 * 设置页只允许管理员进行配置写操作。
 */
const isAdmin = computed(() => authStore.currentUser?.role === "admin");

/**
 * 重新拉取 AI 网关与模型列表。
 */
async function loadGateways(): Promise<void> {
  if (!isAdmin.value) {
    gateways.value = [];
    return;
  }

  loading.value = true;
  error.value = "";

  try {
    const response = await fetchAIGateways();
    gateways.value = response.items.map(mapAIGatewayDto);
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "AI 网关列表加载失败";
  } finally {
    loading.value = false;
  }
}

/**
 * 打开新增网关弹窗。
 */
function openCreateGatewayDialog(presetId: string | null = null): void {
  editingGateway.value = null;
  activeGatewayPresetId.value = presetId;
  gatewayDialogVisible.value = true;
}

/**
 * 打开编辑网关弹窗。
 */
function openEditGatewayDialog(gateway: AIGatewayModel): void {
  editingGateway.value = gateway;
  activeGatewayPresetId.value = null;
  gatewayDialogVisible.value = true;
}

/**
 * 提交网关新增或编辑。
 */
async function handleGatewaySubmit(
  payload: AIGatewayCreateRequestDto | AIGatewayUpdateRequestDto,
  selectedCandidates: AIDiscoveredModelCandidate[],
): Promise<void> {
  gatewaySubmitting.value = true;

  try {
    let gatewayId: number | null = null;
    let gatewayBaseUrl = "";

    if (editingGateway.value) {
      const gateway = await updateAIGateway(
        editingGateway.value.id,
        payload as AIGatewayUpdateRequestDto,
      );
      gatewayId = gateway.id;
      gatewayBaseUrl = gateway.base_url;
      ElMessage.success("AI 网关已更新");
    } else {
      const gateway = await createAIGateway(payload as AIGatewayCreateRequestDto);
      gatewayId = gateway.id;
      gatewayBaseUrl = gateway.base_url;
      ElMessage.success("AI 网关已创建");
    }

    if (gatewayId !== null && selectedCandidates.length > 0) {
      const createResults = await Promise.allSettled(
        selectedCandidates.map((candidate) =>
          createAIModel(gatewayId, {
            display_name: candidate.displayName,
            upstream_vendor: candidate.upstreamVendor,
            protocol_type: candidate.protocolType,
            auth_mode: candidate.authMode,
            base_url_override: candidate.baseUrl === gatewayBaseUrl ? null : candidate.baseUrl,
            user_agent: candidate.userAgent,
            model_identifier: candidate.modelIdentifier,
            supports_vision: candidate.supportsVision,
            supports_stream: candidate.supportsStream,
            is_enabled: true,
            note: `自动探测来源：${candidate.sourceLabel}`,
          }),
        ),
      );

      const successCount = createResults.filter((item) => item.status === "fulfilled").length;
      const failedCount = createResults.length - successCount;

      if (successCount > 0 && failedCount === 0) {
        ElMessage.success(`已自动创建 ${successCount} 个模型配置`);
      } else if (successCount > 0) {
        ElMessage.warning(`已创建 ${successCount} 个模型配置，另有 ${failedCount} 个创建失败`);
      } else if (failedCount > 0) {
        ElMessage.error("网关已保存，但自动创建模型失败，请稍后重试");
      }
    }

    gatewayDialogVisible.value = false;
    await loadGateways();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "AI 网关保存失败";
    ElMessage.error(message);
  } finally {
    gatewaySubmitting.value = false;
  }
}

/**
 * 删除指定 AI 网关。
 */
async function handleDeleteGateway(gateway: AIGatewayModel): Promise<void> {
  await ElMessageBox.confirm(
    `将删除网关“${gateway.name}”及其下所有模型配置，此操作不可恢复。`,
    "删除 AI 网关",
    {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    },
  );

  try {
    await deleteAIGateway(gateway.id);
    ElMessage.success("AI 网关已删除");
    await loadGateways();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "删除 AI 网关失败";
    ElMessage.error(message);
  }
}

/**
 * 切换网关启停状态。
 */
async function toggleGatewayStatus(gateway: AIGatewayModel): Promise<void> {
  try {
    await updateAIGateway(gateway.id, {
      is_enabled: !gateway.isEnabled,
    });
    ElMessage.success(gateway.isEnabled ? "AI 网关已停用" : "AI 网关已启用");
    await loadGateways();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "切换网关状态失败";
    ElMessage.error(message);
  }
}

/**
 * 打开新增模型弹窗。
 */
function openCreateModelDialog(gatewayId: number, templateId: string | null = null): void {
  activeModelGatewayId.value = gatewayId;
  activeModelTemplateId.value = templateId;
  editingModel.value = null;
  modelDialogVisible.value = true;
}

/**
 * 打开编辑模型弹窗。
 */
function openEditModelDialog(gatewayId: number, model: AIModelProfile): void {
  activeModelGatewayId.value = gatewayId;
  activeModelTemplateId.value = null;
  editingModel.value = model;
  modelDialogVisible.value = true;
}

/**
 * 提交模型新增或编辑。
 */
async function handleModelSubmit(
  payload: AIModelProfileCreateRequestDto | AIModelProfileUpdateRequestDto,
): Promise<void> {
  modelSubmitting.value = true;

  try {
    if (editingModel.value) {
      await updateAIModel(editingModel.value.id, payload as AIModelProfileUpdateRequestDto);
      ElMessage.success("模型配置已更新");
    } else if (activeModelGatewayId.value !== null) {
      await createAIModel(activeModelGatewayId.value, payload as AIModelProfileCreateRequestDto);
      ElMessage.success("模型配置已创建");
    }
    modelDialogVisible.value = false;
    await loadGateways();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "模型配置保存失败";
    ElMessage.error(message);
  } finally {
    modelSubmitting.value = false;
  }
}

/**
 * 删除指定模型配置。
 */
async function handleDeleteModel(model: AIModelProfile): Promise<void> {
  await ElMessageBox.confirm(
    `将删除模型配置“${model.displayName}”，此操作不可恢复。`,
    "删除模型配置",
    {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    },
  );

  try {
    await deleteAIModel(model.id);
    ElMessage.success("模型配置已删除");
    await loadGateways();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "删除模型配置失败";
    ElMessage.error(message);
  }
}

/**
 * 切换模型启停状态。
 */
async function toggleModelStatus(model: AIModelProfile): Promise<void> {
  try {
    await updateAIModel(model.id, {
      is_enabled: !model.isEnabled,
    });
    ElMessage.success(model.isEnabled ? "模型配置已停用" : "模型配置已启用");
    await loadGateways();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "切换模型状态失败";
    ElMessage.error(message);
  }
}

/**
 * 返回模型最终会使用的 Base URL。
 */
function resolveModelBaseUrl(gateway: AIGatewayModel, model: AIModelProfile): string {
  return model.baseUrlOverride ?? gateway.baseUrl;
}

/**
 * 根据模型品牌枚举返回展示文本。
 */
function getModelVendorLabel(vendor: AIModelProfile["upstreamVendor"]): string {
  return modelVendorLabels[vendor];
}

/**
 * 根据协议枚举返回展示文本。
 */
function getProtocolLabel(protocol: AIModelProfile["protocolType"]): string {
  return protocolLabels[protocol];
}

/**
 * 根据鉴权方式枚举返回展示文本。
 */
function getAuthModeLabel(authMode: AIModelProfile["authMode"]): string {
  return authModeLabels[authMode];
}

/**
 * 返回指定网关可直接套用的模型模板。
 */
function getGatewayTemplates(vendor: AIGatewayModel["vendor"]) {
  return getModelTemplatesForGatewayVendor(vendor);
}

watch(
  () => isAdmin.value,
  (nextValue) => {
    if (nextValue) {
      void loadGateways();
    }
  },
);

onMounted(() => {
  if (isAdmin.value) {
    void loadGateways();
  }
});
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Settings"
      title="AI 网关与模型配置"
      description="AI URL、Key、User-Agent、协议和模型都由后端托管。前端只拿掩码和运行时可选模型，不能直接拿到真实密钥。像 OpenClaudeCode 这种同站点多协议、多 UA、多 Base URL 规则的中转，也在这里统一管理。"
    />

    <ElAlert
      v-if="!isAdmin"
      type="warning"
      show-icon
      :closable="false"
      title="当前账号不是管理员"
      description="只有管理员可以查看和修改 AI 网关、API Key、模型模板等系统级配置。"
    />

    <ElAlert
      v-else-if="error"
      type="error"
      show-icon
      :closable="false"
      :title="error"
    />

    <template v-if="isAdmin">
      <section class="app-panel settings-panel">
        <div class="settings-panel__header">
          <div>
            <strong>配置原则</strong>
            <p class="muted-text">
              网关负责保存 URL 与 Key，模型负责保存协议、User-Agent、模型标识和 Base URL 覆盖。这样才能正确承载 OpenClaudeCode 的 Claude / Codex / 国产模型三种外接规则。
            </p>
          </div>
          <div class="settings-panel__actions">
            <ElButton @click="loadGateways" :loading="loading">刷新</ElButton>
            <ElButton type="primary" @click="openCreateGatewayDialog()">新增网关</ElButton>
          </div>
        </div>

        <div class="preset-grid">
          <article
            v-for="preset in aiGatewayPresets"
            :key="preset.id"
            class="preset-card"
          >
            <div class="preset-card__body">
              <strong>{{ preset.title }}</strong>
              <p class="muted-text">{{ preset.summary }}</p>
              <div class="preset-card__tags">
                <ElTag effect="dark" round>{{ gatewayVendorLabels[preset.payload.vendor] }}</ElTag>
                <ElTag v-if="preset.payload.base_url" type="info" effect="plain" round>
                  {{ preset.payload.base_url }}
                </ElTag>
              </div>
            </div>
            <ElButton type="primary" plain @click="openCreateGatewayDialog(preset.id)">
              用此预设新建
            </ElButton>
          </article>
        </div>
      </section>

      <section class="page-grid">
        <article
          v-for="gateway in gateways"
          :key="gateway.id"
          class="app-panel gateway-card"
        >
          <div class="gateway-card__header">
            <div class="gateway-card__title">
              <strong>{{ gateway.name }}</strong>
              <div class="gateway-card__tags">
                <ElTag effect="dark" round>{{ gatewayVendorLabels[gateway.vendor] }}</ElTag>
                <ElTag :type="gateway.isEnabled ? 'success' : 'info'" effect="dark" round>
                  {{ gateway.isEnabled ? "启用" : "停用" }}
                </ElTag>
                <ElTag v-if="gateway.apiKeyMask" type="warning" effect="plain" round>
                  {{ gateway.apiKeyMask }}
                </ElTag>
              </div>
            </div>

            <div class="gateway-card__actions">
              <ElButton text type="primary" @click="openEditGatewayDialog(gateway)">编辑网关</ElButton>
              <ElButton text @click="toggleGatewayStatus(gateway)">
                {{ gateway.isEnabled ? "停用" : "启用" }}
              </ElButton>
              <ElButton text type="danger" @click="handleDeleteGateway(gateway)">删除</ElButton>
            </div>
          </div>

          <ElDescriptions :column="2" border>
            <ElDescriptionsItem label="基础 URL">
              {{ gateway.baseUrl }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="官方文档">
              {{ gateway.officialUrl ?? "未填写" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="密钥状态">
              {{ gateway.hasApiKey ? gateway.apiKeyMask ?? "已配置" : "未配置" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="更新时间">
              {{ formatDateTime(gateway.updatedAt) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="备注" :span="2">
              {{ gateway.note ?? "未填写" }}
            </ElDescriptionsItem>
          </ElDescriptions>

          <div class="gateway-card__model-toolbar">
            <div>
              <strong>模型配置</strong>
              <p class="muted-text">
                同一个网关下可以挂多个模型配置，每个模型都可以有自己的协议、Base URL 覆盖和 User-Agent。
              </p>
            </div>
            <div class="gateway-card__actions">
              <ElButton type="primary" plain @click="openCreateModelDialog(gateway.id)">
                新增模型
              </ElButton>
              <ElButton
                v-for="template in getGatewayTemplates(gateway.vendor)"
                :key="template.id"
                plain
                @click="openCreateModelDialog(gateway.id, template.id)"
              >
                {{ template.title }}
              </ElButton>
            </div>
          </div>

          <ElTable
            :data="gateway.models"
            empty-text="当前网关还没有配置模型"
            class="gateway-card__table"
          >
            <ElTableColumn prop="displayName" label="显示名" min-width="180" />
            <ElTableColumn label="模型品牌" min-width="120">
              <template #default="{ row }">
                {{ getModelVendorLabel(row.upstreamVendor) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="协议" min-width="170">
              <template #default="{ row }">
                {{ getProtocolLabel(row.protocolType) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="鉴权" min-width="150">
              <template #default="{ row }">
                {{ getAuthModeLabel(row.authMode) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="最终 Base URL" min-width="220">
              <template #default="{ row }">
                {{ resolveModelBaseUrl(gateway, row) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="User-Agent" min-width="260">
              <template #default="{ row }">
                {{ row.userAgent ?? "未配置" }}
              </template>
            </ElTableColumn>
            <ElTableColumn prop="modelIdentifier" label="模型标识" min-width="180" />
            <ElTableColumn label="能力" min-width="140">
              <template #default="{ row }">
                <div class="ability-tags">
                  <ElTag size="small" :type="row.supportsVision ? 'success' : 'info'" effect="plain" round>
                    {{ row.supportsVision ? "视觉" : "文本" }}
                  </ElTag>
                  <ElTag size="small" :type="row.supportsStream ? 'primary' : 'info'" effect="plain" round>
                    {{ row.supportsStream ? "流式" : "非流式" }}
                  </ElTag>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="状态" min-width="100">
              <template #default="{ row }">
                <ElTag :type="row.isEnabled ? 'success' : 'info'" effect="dark" round>
                  {{ row.isEnabled ? "启用" : "停用" }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" min-width="160">
              <template #default="{ row }">
                <div class="table-actions">
                  <ElButton text type="primary" @click="openEditModelDialog(gateway.id, row)">编辑</ElButton>
                  <ElButton text @click="toggleModelStatus(row)">
                    {{ row.isEnabled ? "停用" : "启用" }}
                  </ElButton>
                  <ElButton text type="danger" @click="handleDeleteModel(row)">删除</ElButton>
                </div>
              </template>
            </ElTableColumn>
          </ElTable>
        </article>

        <section v-if="!loading && gateways.length === 0" class="app-panel gateway-card">
          <ElEmpty description="还没有 AI 网关配置，先从上面的预设或“新增网关”开始。" />
        </section>
      </section>
    </template>

    <AIGatewayFormDialog
      v-model="gatewayDialogVisible"
      :submitting="gatewaySubmitting"
      :initial-value="editingGateway"
      :preset-id="activeGatewayPresetId"
      @submit="handleGatewaySubmit"
    />

    <AIModelFormDialog
      v-model="modelDialogVisible"
      :gateway-id="activeModelGatewayId"
      :submitting="modelSubmitting"
      :initial-value="editingModel"
      :template-id="activeModelTemplateId"
      @submit="handleModelSubmit"
    />
  </div>
</template>

<style scoped>
.settings-panel,
.gateway-card {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.settings-panel__header,
.gateway-card__header,
.gateway-card__model-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.settings-panel__actions,
.gateway-card__actions,
.table-actions,
.gateway-card__tags,
.ability-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  grid-auto-rows: 1fr;
  gap: 16px;
}

.preset-card {
  display: grid;
  grid-template-rows: 1fr auto;
  gap: 16px;
  min-width: 0;
  height: 100%;
  min-height: 230px;
  padding: 18px;
  border: 1px solid var(--el-border-color);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  overflow: hidden;
}

.preset-card__body,
.gateway-card__title {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.preset-card__body {
  align-content: start;
}

.preset-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.preset-card :deep(.el-button) {
  width: 100%;
  margin-left: 0;
}

.preset-card__tags :deep(.el-tag) {
  max-width: 100%;
}

.preset-card__tags :deep(.el-tag__content) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gateway-card__table {
  width: 100%;
}

@media (max-width: 900px) {
  .settings-panel__header,
  .gateway-card__header,
  .gateway-card__model-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
