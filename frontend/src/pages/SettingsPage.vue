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
  fetchSystemUsers,
  updateAIGateway,
  updateAIModel,
  updateSystemUserAiPermission,
} from "@/services/api/settings";
import {
  mapAIGatewayDto,
  mapSystemUserListItemDto,
} from "@/services/mappers/commonMappers";
import { useAuthStore } from "@/stores/auth";
import type {
  AIGatewayCreateRequestDto,
  AIGatewayUpdateRequestDto,
  AIModelProfileCreateRequestDto,
  AIModelProfileUpdateRequestDto,
  UserRole,
} from "@/types/api";
import type {
  AIDiscoveredModelCandidate,
  AIGatewayModel,
  AIModelProfile,
  SystemUserListItem,
} from "@/types/models";
import { formatDateTime } from "@/utils/format";

type SettingsTabName = "account" | "users" | "gateways";
type UserAiFilter = "all" | "enabled" | "disabled";
type UserStatusFilter = "all" | "active" | "inactive";
type UserRoleFilter = UserRole | "all";

const authStore = useAuthStore();
const activeTab = ref<SettingsTabName>("account");

const loading = ref(false);
const gatewaySubmitting = ref(false);
const modelSubmitting = ref(false);
const gatewayError = ref("");
const gateways = ref<AIGatewayModel[]>([]);
const selectedGatewayId = ref<number | null>(null);

const usersLoading = ref(false);
const usersError = ref("");
const users = ref<SystemUserListItem[]>([]);
const usersTotal = ref(0);
const usersCurrentPage = ref(1);
const usersPageSize = ref(10);
const updatingUserIds = ref<number[]>([]);
const userKeyword = ref("");
const userRoleFilter = ref<UserRoleFilter>("all");
const userAiFilter = ref<UserAiFilter>("all");
const userStatusFilter = ref<UserStatusFilter>("all");

const gatewayDialogVisible = ref(false);
const editingGateway = ref<AIGatewayModel | null>(null);
const activeGatewayPresetId = ref<string | null>(null);

const modelDialogVisible = ref(false);
const editingModel = ref<AIModelProfile | null>(null);
const activeModelTemplateId = ref<string | null>(null);
const activeModelGatewayId = ref<number | null>(null);

/**
 * 只有管理员可以进入系统级配置区。
 */
const isAdmin = computed(() => authStore.currentUser?.role === "admin");

/**
 * 当前账号是否已开通 AI 分析。
 * 用户侧要能在系统设置里直接看到自己的授权状态。
 */
const canUseAiAnalysis = computed(() => authStore.currentUser?.canUseAiAnalysis ?? false);

/**
 * 当前右侧详情区展示的网关对象。
 * 网关列表增多时，只保留一个活动详情，避免整页长卡片堆叠。
 */
const activeGateway = computed<AIGatewayModel | null>(() => {
  if (gateways.value.length === 0) {
    return null;
  }

  return gateways.value.find((item) => item.id === selectedGatewayId.value) ?? gateways.value[0];
});

/**
 * 管理员用户列表的总页数。
 */
const usersPageCount = computed(() =>
  Math.max(Math.ceil(usersTotal.value / usersPageSize.value), 1),
);

/**
 * 返回角色中文标签，避免模板里散落枚举判断。
 */
function getRoleLabel(role: UserRole): string {
  if (role === "admin") {
    return "管理员";
  }
  if (role === "reviewer") {
    return "复核员";
  }
  return "操作员";
}

/**
 * 返回账号状态标签文本。
 */
function getUserStatusLabel(isActive: boolean): string {
  return isActive ? "启用中" : "已停用";
}

/**
 * 返回指定用户当前是否正在切换 AI 权限。
 */
function isUpdatingUserPermission(userId: number): boolean {
  return updatingUserIds.value.includes(userId);
}

/**
 * 确保网关详情区始终有一个合法选中项。
 * 删除、刷新或首次加载后都要调用，避免右侧详情指向一个已经不存在的网关。
 */
function syncSelectedGateway(nextGateways: AIGatewayModel[]): void {
  if (nextGateways.length === 0) {
    selectedGatewayId.value = null;
    return;
  }

  if (!nextGateways.some((item) => item.id === selectedGatewayId.value)) {
    selectedGatewayId.value = nextGateways[0].id;
  }
}

/**
 * 拉取 AI 网关与模型配置。
 */
async function loadGateways(): Promise<void> {
  if (!isAdmin.value) {
    gateways.value = [];
    selectedGatewayId.value = null;
    return;
  }

  loading.value = true;
  gatewayError.value = "";

  try {
    const response = await fetchAIGateways();
    const nextGateways = response.items.map(mapAIGatewayDto);
    gateways.value = nextGateways;
    syncSelectedGateway(nextGateways);
  } catch (caughtError) {
    gatewayError.value = caughtError instanceof Error ? caughtError.message : "AI 网关列表加载失败";
  } finally {
    loading.value = false;
  }
}

/**
 * 拉取管理员用户列表。
 * 这里把搜索、筛选和分页都交给后端，避免用户数量变大后前端一次性加载全部账号。
 */
async function loadSystemUsers(): Promise<void> {
  if (!isAdmin.value) {
    users.value = [];
    usersTotal.value = 0;
    usersError.value = "";
    return;
  }

  usersLoading.value = true;
  usersError.value = "";

  try {
    const response = await fetchSystemUsers({
      keyword: userKeyword.value.trim() || undefined,
      role: userRoleFilter.value === "all" ? undefined : userRoleFilter.value,
      aiEnabled:
        userAiFilter.value === "all"
          ? undefined
          : userAiFilter.value === "enabled",
      isActive:
        userStatusFilter.value === "all"
          ? undefined
          : userStatusFilter.value === "active",
      skip: (usersCurrentPage.value - 1) * usersPageSize.value,
      limit: usersPageSize.value,
    });
    users.value = response.items.map(mapSystemUserListItemDto);
    usersTotal.value = response.total;
  } catch (caughtError) {
    usersError.value = caughtError instanceof Error ? caughtError.message : "用户列表加载失败";
  } finally {
    usersLoading.value = false;
  }
}

/**
 * 进入指定网关详情。
 */
function selectGateway(gatewayId: number): void {
  selectedGatewayId.value = gatewayId;
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
 * 新建成功时，会顺手把自动探测出的模型一并写入，减少管理员重复操作。
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
          createAIModel(gatewayId!, {
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
    if (gatewayId !== null) {
      selectedGatewayId.value = gatewayId;
    }
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
 * 提交用户筛选查询。
 */
async function handleUserSearch(): Promise<void> {
  usersCurrentPage.value = 1;
  await loadSystemUsers();
}

/**
 * 重置管理员用户管理筛选条件。
 */
async function handleResetUserFilters(): Promise<void> {
  userKeyword.value = "";
  userRoleFilter.value = "all";
  userAiFilter.value = "all";
  userStatusFilter.value = "all";
  usersCurrentPage.value = 1;
  await loadSystemUsers();
}

/**
 * 切换管理员用户列表页码。
 */
async function handleUserPageChange(page: number): Promise<void> {
  usersCurrentPage.value = page;
  await loadSystemUsers();
}

/**
 * 切换管理员用户列表分页大小。
 */
async function handleUserPageSizeChange(pageSize: number): Promise<void> {
  usersPageSize.value = pageSize;
  usersCurrentPage.value = 1;
  await loadSystemUsers();
}

/**
 * 修改指定用户的 AI 使用权限。
 * 如果管理员修改的是当前登录账号，会同步刷新 Pinia 中的本地会话状态。
 */
async function handleToggleUserAiPermission(
  user: SystemUserListItem,
  nextValue: boolean,
): Promise<void> {
  if (isUpdatingUserPermission(user.id)) {
    return;
  }

  updatingUserIds.value = [...updatingUserIds.value, user.id];

  try {
    await updateSystemUserAiPermission(user.id, {
      can_use_ai_analysis: nextValue,
    });

    if (authStore.currentUser?.id === user.id) {
      authStore.currentUser = {
        ...authStore.currentUser,
        canUseAiAnalysis: nextValue,
      };
    }

    ElMessage.success(nextValue ? "已开启该用户的 AI 分析权限" : "已关闭该用户的 AI 分析权限");
    await loadSystemUsers();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "用户 AI 权限更新失败";
    ElMessage.error(message);
  } finally {
    updatingUserIds.value = updatingUserIds.value.filter((item) => item !== user.id);
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
    if (!nextValue) {
      activeTab.value = "account";
      gateways.value = [];
      users.value = [];
      usersTotal.value = 0;
      selectedGatewayId.value = null;
      return;
    }

    void Promise.all([loadGateways(), loadSystemUsers()]);
  },
);

onMounted(() => {
  if (isAdmin.value) {
    void Promise.all([loadGateways(), loadSystemUsers()]);
  }
});
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Settings"
      title="系统设置"
      description="这里把账号状态、用户 AI 权限和 AI 网关配置拆成独立工作区。普通用户可以查看自己的基础信息与授权状态；管理员则在同一页里集中管理用户权限和网关模型。"
    />

    <ElTabs v-model="activeTab" class="settings-tabs">
      <ElTabPane label="基础信息" name="account">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>当前账号</strong>
              <p class="muted-text">
                用户端可以在这里直接确认自己的身份、账号状态和 AI 分析授权状态。
              </p>
            </div>
            <div class="settings-panel__status-tags">
              <ElTag
                :type="authStore.currentUser?.isActive ? 'success' : 'danger'"
                effect="dark"
                round
              >
                {{ authStore.currentUser?.isActive ? "账号启用中" : "账号已停用" }}
              </ElTag>
              <ElTag
                :type="canUseAiAnalysis ? 'success' : 'warning'"
                effect="dark"
                round
              >
                {{ canUseAiAnalysis ? "AI 分析已授权" : "AI 分析未授权" }}
              </ElTag>
              <ElTag effect="plain" round>
                {{ getRoleLabel(authStore.currentUser?.role ?? "operator") }}
              </ElTag>
            </div>
          </div>

          <div class="account-overview">
            <article class="account-summary-card">
              <span class="account-summary-card__label">登录账号</span>
              <strong>{{ authStore.currentUser?.username ?? "未获取" }}</strong>
              <p class="muted-text">用于登录系统的唯一账号标识。</p>
            </article>
            <article class="account-summary-card">
              <span class="account-summary-card__label">显示名称</span>
              <strong>{{ authStore.currentUser?.displayName ?? "未获取" }}</strong>
              <p class="muted-text">界面内展示给业务人员的名称。</p>
            </article>
            <article class="account-summary-card">
              <span class="account-summary-card__label">AI 权限</span>
              <strong>{{ canUseAiAnalysis ? "已开通" : "未开通" }}</strong>
              <p class="muted-text">由管理员在系统设置中单独授予，不会默认开启。</p>
            </article>
          </div>

          <ElDescriptions :column="2" border>
            <ElDescriptionsItem label="用户名">
              {{ authStore.currentUser?.username ?? "未获取" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="显示名称">
              {{ authStore.currentUser?.displayName ?? "未获取" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="邮箱">
              {{ authStore.currentUser?.email ?? "未填写" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="角色">
              {{ getRoleLabel(authStore.currentUser?.role ?? "operator") }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="账号状态">
              {{ getUserStatusLabel(authStore.currentUser?.isActive ?? false) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="AI 分析授权">
              {{ canUseAiAnalysis ? "已授权" : "未授权" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="最近登录">
              {{ formatDateTime(authStore.currentUser?.lastLoginAt ?? null) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="密码最近修改">
              {{ formatDateTime(authStore.currentUser?.passwordChangedAt ?? null) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="创建时间">
              {{ formatDateTime(authStore.currentUser?.createdAt ?? null) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="更新时间">
              {{ formatDateTime(authStore.currentUser?.updatedAt ?? null) }}
            </ElDescriptionsItem>
          </ElDescriptions>

          <ElAlert
            v-if="!isAdmin"
            type="info"
            show-icon
            :closable="false"
            title="当前账号没有系统管理权限"
            description="你可以查看自己的基础信息和 AI 授权状态，但不能管理其他用户，也不能修改网关、模型和密钥配置。"
          />
        </section>
      </ElTabPane>

      <ElTabPane v-if="isAdmin" label="用户管理" name="users">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>用户 AI 权限管理</strong>
              <p class="muted-text">
                新注册用户默认不开放 AI 分析。管理员可以在这里按搜索、角色、状态和 AI 授权状态筛选账号，再决定是否放开 AI。
              </p>
            </div>
            <div class="settings-panel__actions">
              <ElButton @click="loadSystemUsers" :loading="usersLoading">刷新</ElButton>
            </div>
          </div>

          <div class="user-filter-grid">
            <ElInput
              v-model="userKeyword"
              clearable
              placeholder="搜索用户名、显示名称或邮箱"
              @keyup.enter="handleUserSearch"
            />

            <ElSelect v-model="userRoleFilter" placeholder="角色筛选">
              <ElOption label="全部角色" value="all" />
              <ElOption label="管理员" value="admin" />
              <ElOption label="操作员" value="operator" />
              <ElOption label="复核员" value="reviewer" />
            </ElSelect>

            <ElSelect v-model="userAiFilter" placeholder="AI 权限筛选">
              <ElOption label="全部 AI 状态" value="all" />
              <ElOption label="已授权" value="enabled" />
              <ElOption label="未授权" value="disabled" />
            </ElSelect>

            <ElSelect v-model="userStatusFilter" placeholder="账号状态筛选">
              <ElOption label="全部账号状态" value="all" />
              <ElOption label="启用中" value="active" />
              <ElOption label="已停用" value="inactive" />
            </ElSelect>

            <div class="user-filter-grid__actions">
              <ElButton type="primary" :loading="usersLoading" @click="handleUserSearch">
                查询
              </ElButton>
              <ElButton plain @click="handleResetUserFilters">重置</ElButton>
            </div>
          </div>

          <ElAlert
            v-if="usersError"
            type="error"
            show-icon
            :closable="false"
            :title="usersError"
          />

          <ElTable
            :data="users"
            v-loading="usersLoading"
            empty-text="当前筛选条件下没有用户"
            class="settings-table"
          >
            <ElTableColumn label="账号" min-width="220">
              <template #default="{ row }">
                <div class="table-user-cell">
                  <strong>{{ row.displayName }}</strong>
                  <span>{{ row.username }}</span>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="email" label="邮箱" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.email ?? "未填写" }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="角色" min-width="110">
              <template #default="{ row }">
                <ElTag effect="plain" round>{{ getRoleLabel(row.role) }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="账号状态" min-width="110">
              <template #default="{ row }">
                <ElTag :type="row.isActive ? 'success' : 'info'" effect="dark" round>
                  {{ getUserStatusLabel(row.isActive) }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="AI 权限" min-width="150">
              <template #default="{ row }">
                <ElSwitch
                  :model-value="row.canUseAiAnalysis"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                  :loading="isUpdatingUserPermission(row.id)"
                  @change="(value) => handleToggleUserAiPermission(row, Boolean(value))"
                />
              </template>
            </ElTableColumn>
            <ElTableColumn label="最近登录" min-width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.lastLoginAt) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="创建时间" min-width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.createdAt) }}
              </template>
            </ElTableColumn>
          </ElTable>

          <div class="settings-pagination">
            <span class="muted-text">
              共 {{ usersTotal }} 个用户，当前第 {{ usersCurrentPage }} / {{ usersPageCount }} 页
            </span>

            <ElPagination
              background
              layout="prev, pager, next, sizes, total"
              :current-page="usersCurrentPage"
              :page-size="usersPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="usersTotal"
              @current-change="handleUserPageChange"
              @size-change="handleUserPageSizeChange"
            />
          </div>
        </section>
      </ElTabPane>

      <ElTabPane v-if="isAdmin" label="AI 网关" name="gateways">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>AI 网关与模型配置</strong>
              <p class="muted-text">
                URL、Key、协议和 User-Agent 都由后端托管。这里采用“左侧网关列表 + 右侧详情工作区”的方式展示，避免网关变多后整页都是冗长大卡片。
              </p>
            </div>
            <div class="settings-panel__actions">
              <ElButton @click="loadGateways" :loading="loading">刷新</ElButton>
              <ElButton type="primary" @click="openCreateGatewayDialog()">新增网关</ElButton>
            </div>
          </div>

          <ElAlert
            v-if="gatewayError"
            type="error"
            show-icon
            :closable="false"
            :title="gatewayError"
          />

          <div class="gateway-preset-grid">
            <article
              v-for="preset in aiGatewayPresets"
              :key="preset.id"
              class="gateway-preset-card"
            >
              <div class="gateway-preset-card__body">
                <strong>{{ preset.title }}</strong>
                <p class="muted-text">{{ preset.summary }}</p>
                <ElTag effect="plain" round>{{ gatewayVendorLabels[preset.payload.vendor] }}</ElTag>
              </div>
              <ElButton type="primary" plain @click="openCreateGatewayDialog(preset.id)">
                用此预设新建
              </ElButton>
            </article>
          </div>

          <div class="gateway-workspace">
            <aside class="gateway-list">
              <div class="gateway-list__header">
                <strong>网关列表</strong>
                <span class="muted-text">共 {{ gateways.length }} 个</span>
              </div>

              <div v-if="gateways.length === 0" class="gateway-list__empty">
                <ElEmpty description="还没有 AI 网关配置" />
              </div>

              <button
                v-for="gateway in gateways"
                :key="gateway.id"
                type="button"
                class="gateway-summary"
                :class="{ 'gateway-summary--active': gateway.id === activeGateway?.id }"
                @click="selectGateway(gateway.id)"
              >
                <div class="gateway-summary__head">
                  <strong>{{ gateway.name }}</strong>
                  <ElTag :type="gateway.isEnabled ? 'success' : 'info'" effect="dark" round>
                    {{ gateway.isEnabled ? "启用" : "停用" }}
                  </ElTag>
                </div>
                <div class="gateway-summary__tags">
                  <ElTag effect="plain" round>{{ gatewayVendorLabels[gateway.vendor] }}</ElTag>
                  <ElTag effect="plain" round type="info">{{ gateway.models.length }} 个模型</ElTag>
                </div>
                <p class="gateway-summary__url">{{ gateway.baseUrl }}</p>
                <span class="gateway-summary__time">
                  更新于 {{ formatDateTime(gateway.updatedAt) }}
                </span>
              </button>
            </aside>

            <section class="gateway-detail">
              <template v-if="activeGateway">
                <div class="gateway-detail__header">
                  <div>
                    <strong>{{ activeGateway.name }}</strong>
                    <p class="muted-text">
                      右侧只展开当前选中的网关详情和模型列表，减少系统设置页的视觉噪音。
                    </p>
                  </div>
                  <div class="settings-panel__actions">
                    <ElButton text type="primary" @click="openEditGatewayDialog(activeGateway)">
                      编辑网关
                    </ElButton>
                    <ElButton text @click="toggleGatewayStatus(activeGateway)">
                      {{ activeGateway.isEnabled ? "停用" : "启用" }}
                    </ElButton>
                    <ElButton text type="danger" @click="handleDeleteGateway(activeGateway)">
                      删除
                    </ElButton>
                  </div>
                </div>

                <ElDescriptions :column="2" border>
                  <ElDescriptionsItem label="供应商">
                    {{ gatewayVendorLabels[activeGateway.vendor] }}
                  </ElDescriptionsItem>
                  <ElDescriptionsItem label="状态">
                    {{ activeGateway.isEnabled ? "已启用" : "已停用" }}
                  </ElDescriptionsItem>
                  <ElDescriptionsItem label="基础 URL" :span="2">
                    {{ activeGateway.baseUrl }}
                  </ElDescriptionsItem>
                  <ElDescriptionsItem label="官方文档">
                    {{ activeGateway.officialUrl ?? "未填写" }}
                  </ElDescriptionsItem>
                  <ElDescriptionsItem label="密钥状态">
                    {{ activeGateway.hasApiKey ? activeGateway.apiKeyMask ?? "已配置" : "未配置" }}
                  </ElDescriptionsItem>
                  <ElDescriptionsItem label="备注" :span="2">
                    {{ activeGateway.note ?? "未填写" }}
                  </ElDescriptionsItem>
                </ElDescriptions>

                <div class="gateway-detail__models">
                  <div class="gateway-detail__header">
                    <div>
                      <strong>模型配置</strong>
                      <p class="muted-text">
                        同一网关下可以挂多个模型配置，但详情区只显示当前网关的模型，避免所有网关模型一股脑全部摊开。
                      </p>
                    </div>
                    <div class="settings-panel__actions">
                      <ElButton type="primary" plain @click="openCreateModelDialog(activeGateway.id)">
                        新增模型
                      </ElButton>
                      <ElButton
                        v-for="template in getGatewayTemplates(activeGateway.vendor)"
                        :key="template.id"
                        plain
                        @click="openCreateModelDialog(activeGateway.id, template.id)"
                      >
                        {{ template.title }}
                      </ElButton>
                    </div>
                  </div>

                  <ElTable
                    :data="activeGateway.models"
                    empty-text="当前网关还没有配置模型"
                    class="settings-table"
                  >
                    <ElTableColumn prop="displayName" label="显示名" min-width="170" />
                    <ElTableColumn label="模型品牌" min-width="110">
                      <template #default="{ row }">
                        {{ getModelVendorLabel(row.upstreamVendor) }}
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="协议" min-width="150">
                      <template #default="{ row }">
                        {{ getProtocolLabel(row.protocolType) }}
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="鉴权" min-width="140">
                      <template #default="{ row }">
                        {{ getAuthModeLabel(row.authMode) }}
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="最终 Base URL" min-width="220" show-overflow-tooltip>
                      <template #default="{ row }">
                        {{ resolveModelBaseUrl(activeGateway, row) }}
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="模型标识" min-width="180" show-overflow-tooltip>
                      <template #default="{ row }">
                        {{ row.modelIdentifier }}
                      </template>
                    </ElTableColumn>
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
                    <ElTableColumn label="状态" min-width="90">
                      <template #default="{ row }">
                        <ElTag :type="row.isEnabled ? 'success' : 'info'" effect="dark" round>
                          {{ row.isEnabled ? "启用" : "停用" }}
                        </ElTag>
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="操作" min-width="160">
                      <template #default="{ row }">
                        <div class="table-actions">
                          <ElButton text type="primary" @click="openEditModelDialog(activeGateway.id, row)">
                            编辑
                          </ElButton>
                          <ElButton text @click="toggleModelStatus(row)">
                            {{ row.isEnabled ? "停用" : "启用" }}
                          </ElButton>
                          <ElButton text type="danger" @click="handleDeleteModel(row)">
                            删除
                          </ElButton>
                        </div>
                      </template>
                    </ElTableColumn>
                  </ElTable>
                </div>
              </template>

              <div v-else class="gateway-detail__empty">
                <ElEmpty description="请选择左侧网关，或先创建一个新的 AI 网关。" />
              </div>
            </section>
          </div>
        </section>
      </ElTabPane>
    </ElTabs>

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
.gateway-detail,
.gateway-list,
.account-summary-card,
.gateway-preset-card {
  display: grid;
  gap: 16px;
}

.settings-panel {
  padding: 22px;
}

.settings-panel__header,
.settings-panel__actions,
.settings-panel__status-tags,
.gateway-detail__header,
.settings-pagination,
.table-actions,
.ability-tags,
.gateway-summary__head,
.gateway-summary__tags,
.user-filter-grid__actions {
  display: flex;
  gap: 12px;
}

.settings-panel__header,
.gateway-detail__header,
.settings-pagination,
.gateway-summary__head {
  align-items: flex-start;
  justify-content: space-between;
}

.settings-panel__actions,
.settings-panel__status-tags,
.table-actions,
.ability-tags,
.gateway-summary__tags,
.user-filter-grid__actions {
  flex-wrap: wrap;
}

.settings-tabs :deep(.el-tabs__content) {
  padding-top: 6px;
}

.account-overview,
.gateway-preset-grid,
.gateway-workspace,
.user-filter-grid {
  display: grid;
  gap: 16px;
}

.account-overview {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.account-summary-card {
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.08), transparent 34%),
    rgba(255, 255, 255, 0.02);
}

.account-summary-card__label {
  color: var(--app-text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.account-summary-card p {
  margin: 0;
  line-height: 1.7;
}

.user-filter-grid {
  grid-template-columns: minmax(240px, 1.4fr) repeat(3, minmax(180px, 1fr)) auto;
  align-items: center;
}

.settings-table {
  width: 100%;
}

.table-user-cell {
  display: grid;
  gap: 6px;
}

.table-user-cell span {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.gateway-preset-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.gateway-preset-card {
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
}

.gateway-preset-card__body {
  display: grid;
  gap: 10px;
}

.gateway-preset-card__body p {
  margin: 0;
  line-height: 1.7;
}

.gateway-workspace {
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  align-items: start;
}

.gateway-list,
.gateway-detail {
  min-height: 100%;
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.02);
}

.gateway-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.gateway-list__empty,
.gateway-detail__empty {
  min-height: 220px;
  display: grid;
  place-items: center;
}

.gateway-summary {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  color: var(--app-text);
  text-align: left;
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.gateway-summary:hover {
  transform: translateY(-1px);
  border-color: rgba(127, 228, 208, 0.34);
}

.gateway-summary--active {
  border-color: rgba(127, 228, 208, 0.48);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 36%),
    rgba(255, 255, 255, 0.03);
}

.gateway-summary__url,
.gateway-summary__time {
  margin: 0;
  color: var(--app-text-secondary);
}

.gateway-summary__url {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.gateway-summary__time {
  font-size: 12px;
}

.gateway-detail__models {
  display: grid;
  gap: 16px;
}

.settings-pagination {
  flex-wrap: wrap;
}

@media (max-width: 1280px) {
  .gateway-workspace,
  .account-overview,
  .user-filter-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .settings-panel__header,
  .gateway-detail__header,
  .settings-pagination {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
