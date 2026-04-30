<script setup lang="ts">
import { computed, ref, watch } from "vue";
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
  approveCompanyAdminApplication,
  deactivateCompany,
  fetchCompanies,
  fetchCompanyAdminApplications,
  fetchCurrentCompany,
  purgeCompany,
  rejectCompanyAdminApplication,
  resetCurrentCompanyInviteCode,
} from "@/services/api/companies";
import {
  approveSystemUserPasswordChangeRequest,
  createAIGateway,
  createAIModel,
  deleteSystemUser,
  deleteAIGateway,
  deleteAIModel,
  fetchAIGateways,
  fetchCurrentUserPasswordChangeRequest,
  fetchSystemUsers,
  rejectSystemUserPasswordChangeRequest,
  submitCurrentUserPasswordChangeRequest,
  updateAIGateway,
  updateAIModel,
  updateSystemUserAiPermission,
  updateSystemUserStatus,
} from "@/services/api/settings";
import { ApiClientError } from "@/services/api/client";
import {
  mapAIGatewayDto,
  mapCompanyAdminApplicationItemDto,
  mapCompanySummaryResponseDto,
  mapCurrentCompanyResponseDto,
  mapSystemUserListItemDto,
  mapUserPasswordChangeRequestInfoDto,
} from "@/services/mappers/commonMappers";
import { useAuthStore } from "@/stores/auth";
import type {
  AIGatewayCreateRequestDto,
  AIGatewayUpdateRequestDto,
  AIModelProfileCreateRequestDto,
  AIModelProfileUpdateRequestDto,
  AdminApplicationStatus,
  PasswordChangeRequestStatus,
  PasswordChangeRequestType,
  UserRole,
} from "@/types/api";
import type {
  AIDiscoveredModelCandidate,
  AIGatewayModel,
  AIModelProfile,
  CompanyAdminApplicationItem,
  CompanySummary,
  CurrentCompany,
  SystemUserListItem,
  UserPasswordChangeRequestInfo,
} from "@/types/models";
import { formatDateTime } from "@/utils/format";

type SettingsTabName =
  | "account"
  | "company"
  | "users"
  | "applications"
  | "companies"
  | "gateways";
type UserAiFilter = "all" | "enabled" | "disabled";
type UserStatusFilter = "all" | "active" | "inactive";
type UserRoleFilter = UserRole | "all";
type CompanyApplicationFilter = AdminApplicationStatus | "all";
type CompanyActiveFilter = "all" | "active" | "inactive";

const authStore = useAuthStore();
const activeTab = ref<SettingsTabName>("account");

// 当前公司详情与邀请码相关状态。
const currentCompanyLoading = ref(false);
const currentCompanyError = ref("");
const currentCompany = ref<CurrentCompany | null>(null);
const inviteCodeResetting = ref(false);

// AI 网关与模型配置区状态。
const loading = ref(false);
const gatewaySubmitting = ref(false);
const modelSubmitting = ref(false);
const gatewayError = ref("");
// 这里单独保存“弹窗提交失败”的状态，避免和列表加载错误混在一起。
const gatewaySubmitError = ref("");
const gatewaySubmitErrorCode = ref("");
const gateways = ref<AIGatewayModel[]>([]);
const selectedGatewayId = ref<number | null>(null);

// 公司内用户管理状态。
const usersLoading = ref(false);
const usersError = ref("");
const users = ref<SystemUserListItem[]>([]);
const usersTotal = ref(0);
const usersCurrentPage = ref(1);
const usersPageSize = ref(10);
// 用户管理表中的各种行级操作都复用这一组 loading 标记，避免重复提交。
const updatingUserIds = ref<number[]>([]);
const userKeyword = ref("");
const userRoleFilter = ref<UserRoleFilter>("all");
const userAiFilter = ref<UserAiFilter>("all");
const userStatusFilter = ref<UserStatusFilter>("all");

// 当前登录用户在“基础信息”页里看到的站内改密申请状态与表单。
const passwordRequestLoading = ref(false);
const passwordRequestSubmitting = ref(false);
const passwordRequestInfo = ref<UserPasswordChangeRequestInfo | null>(null);
const passwordRequestForm = ref({
  newPassword: "",
  confirmPassword: "",
});

// 平台管理员审批“新公司管理员申请”的状态。
const applicationsLoading = ref(false);
const applicationsError = ref("");
const applications = ref<CompanyAdminApplicationItem[]>([]);
const applicationsTotal = ref(0);
const applicationsCurrentPage = ref(1);
const applicationsPageSize = ref(10);
const applicationKeyword = ref("");
const applicationStatusFilter = ref<CompanyApplicationFilter>("pending");

// 平台管理员查看公司列表、停用与彻底删除的状态。
const companiesLoading = ref(false);
const companiesError = ref("");
const companies = ref<CompanySummary[]>([]);
const companiesTotal = ref(0);
const companiesCurrentPage = ref(1);
const companiesPageSize = ref(10);
const companyKeyword = ref("");
const companyActiveFilter = ref<CompanyActiveFilter>("all");

// AI 网关和模型编辑弹窗状态。
const gatewayDialogVisible = ref(false);
const editingGateway = ref<AIGatewayModel | null>(null);
const activeGatewayPresetId = ref<string | null>(null);

const modelDialogVisible = ref(false);
const editingModel = ref<AIModelProfile | null>(null);
const activeModelTemplateId = ref<string | null>(null);
const activeModelGatewayId = ref<number | null>(null);

/**
 * 只要角色是 admin，就视为当前用户具备公司级管理权限。
 * 公司内用户管理、邀请码与 AI 网关配置都属于公司管理员职责。
 */
const isCompanyAdmin = computed(() => authStore.currentUser?.role === "admin");

/**
 * 平台默认管理员拥有跨公司审批和回收权限。
 * 只有这一类账号能看到“平台审批”和“公司管理”两块。
 */
const isPlatformAdmin = computed(() => authStore.currentUser?.isDefaultAdmin ?? false);

/**
 * 当前账号是否已获得 AI 分析权限。
 * 普通用户和管理员都需要能在设置页直接看到这个结果。
 */
const canUseAiAnalysis = computed(() => authStore.currentUser?.canUseAiAnalysis ?? false);

/**
 * 当前登录用户最近一次站内密码申请的状态。
 * 账号页里的展示和按钮禁用都依赖这一层派生状态，避免模板里重复写空值兜底。
 */
const currentPasswordRequestStatus = computed<PasswordChangeRequestStatus | null>(
  () => passwordRequestInfo.value?.passwordChangeRequestStatus ?? null,
);

/**
 * 当前登录用户最近一次站内密码申请的类型。
 */
const currentPasswordRequestType = computed<PasswordChangeRequestType | null>(
  () => passwordRequestInfo.value?.passwordChangeRequestType ?? null,
);

/**
 * 站内默认重置密码提示文案。
 * 后端会返回真实默认值，这里只保留最后一道兜底，避免页面在未加载完成前出现空文案。
 */
const defaultResetPasswordLabel = computed(
  () => passwordRequestInfo.value?.defaultResetPassword ?? "Q123456@",
);

/**
 * 当前登录用户是否已经有一条待审批的密码申请。
 * 待审批时前端直接禁用再次提交，防止用户误以为可以叠加多条申请。
 */
const isCurrentPasswordRequestPending = computed(
  () => currentPasswordRequestStatus.value === "pending",
);

/**
 * 当前展示给页面的公司名称。
 * 如果公司详情接口还没返回，先退回到登录态里附带的公司简要信息。
 */
const companyDisplayName = computed(
  () => currentCompany.value?.name ?? authStore.currentUser?.company?.name ?? "未归属公司",
);

/**
 * 当前公司详情区展示的网关对象。
 * 左侧只负责选择，右侧只展开一个当前网关，避免页面信息过载。
 */
const activeGateway = computed<AIGatewayModel | null>(() => {
  if (gateways.value.length === 0) {
    return null;
  }

  return gateways.value.find((item) => item.id === selectedGatewayId.value) ?? gateways.value[0];
});

/**
 * 当前公司里已启用的 AI 网关数量。
 * 左侧列表区会把它作为概览数字展示，避免只有一张卡时留出大块无意义空白。
 */
const enabledGatewayCount = computed(
  () => gateways.value.filter((gateway) => gateway.isEnabled).length,
);

/**
 * 当前选中网关下挂载的模型数量。
 * 这个数字放在列表概览里，帮助用户在切换详情前先看到当前网关规模。
 */
const activeGatewayModelCount = computed(() => activeGateway.value?.models.length ?? 0);

/**
 * 当前详情区真正参与渲染的模型列表。
 * 后续分页、统计和表格展示都只消费这一份派生结果，避免模板层到处写空值兜底。
 */
const activeGatewayModels = computed(() => activeGateway.value?.models ?? []);

/**
 * 模型列表分页状态。
 * 当前网关模型变多后，详情区不再一次性把所有模型全部摊开，避免页面被拉成长表。
 */
const gatewayModelCurrentPage = ref(1);
const gatewayModelPageSize = ref(6);

/**
 * 详情区模型概览指标。
 * 这些数字会放在模型表上方，帮助用户先看规模和能力分布，再决定是否继续翻页查看明细。
 */
const activeGatewayEnabledModelCount = computed(
  () => activeGatewayModels.value.filter((model) => model.isEnabled).length,
);
const activeGatewayVisionModelCount = computed(
  () => activeGatewayModels.value.filter((model) => model.supportsVision).length,
);
const activeGatewayStreamingModelCount = computed(
  () => activeGatewayModels.value.filter((model) => model.supportsStream).length,
);

/**
 * 当前模型表的总页数与实际生效页码。
 * 切换网关或缩小模型数量后，页码会自动回落到有效范围内，避免出现空页。
 */
const gatewayModelPageCount = computed(() =>
  Math.max(Math.ceil(activeGatewayModels.value.length / gatewayModelPageSize.value), 1),
);
const normalizedGatewayModelCurrentPage = computed(() =>
  Math.min(gatewayModelCurrentPage.value, gatewayModelPageCount.value),
);

/**
 * 当前页真正显示的模型数据。
 * 详情表格只渲染这一小段切片，控制页面纵向长度。
 */
const pagedActiveGatewayModels = computed(() => {
  const startIndex = (normalizedGatewayModelCurrentPage.value - 1) * gatewayModelPageSize.value;
  return activeGatewayModels.value.slice(startIndex, startIndex + gatewayModelPageSize.value);
});

/**
 * 用户管理列表总页数。
 */
const usersPageCount = computed(() =>
  Math.max(Math.ceil(usersTotal.value / usersPageSize.value), 1),
);

/**
 * 平台审批列表总页数。
 */
const applicationsPageCount = computed(() =>
  Math.max(Math.ceil(applicationsTotal.value / applicationsPageSize.value), 1),
);

/**
 * 公司列表总页数。
 */
const companiesPageCount = computed(() =>
  Math.max(Math.ceil(companiesTotal.value / companiesPageSize.value), 1),
);

/**
 * 切换模型列表页码。
 */
function handleGatewayModelPageChange(nextPage: number): void {
  gatewayModelCurrentPage.value = nextPage;
}

/**
 * 切换模型列表每页数量。
 * 一旦页尺寸变化，直接回到第一页，避免用户停留在一个已经越界的旧页码上。
 */
function handleGatewayModelPageSizeChange(nextPageSize: number): void {
  gatewayModelPageSize.value = nextPageSize;
  gatewayModelCurrentPage.value = 1;
}

/**
 * 返回角色中文标签。
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
 * 返回账号启停状态标签。
 */
function getUserStatusLabel(isActive: boolean): string {
  return isActive ? "启用中" : "已停用";
}

/**
 * 返回站内改密申请状态标签。
 */
function getPasswordRequestStatusLabel(
  status: PasswordChangeRequestStatus | null,
): string {
  if (status === "pending") {
    return "待审批";
  }
  if (status === "approved") {
    return "已批准";
  }
  if (status === "rejected") {
    return "已拒绝";
  }
  return "未提交";
}

/**
 * 返回站内改密申请类型标签。
 */
function getPasswordRequestTypeLabel(type: PasswordChangeRequestType | null): string {
  if (type === "reset_to_default") {
    return "重置为默认密码";
  }
  if (type === "change_to_requested") {
    return "改成申请的新密码";
  }
  return "暂无";
}

/**
 * 根据站内改密申请状态返回展示色。
 */
function getPasswordRequestTagType(
  status: PasswordChangeRequestStatus | null,
): "warning" | "success" | "danger" | "info" {
  if (status === "pending") {
    return "warning";
  }
  if (status === "approved") {
    return "success";
  }
  if (status === "rejected") {
    return "danger";
  }
  return "info";
}

/**
 * 判断表格里的这一行是否就是当前登录账号。
 * 自己的账号不允许被自己停用、删除或自审改密申请，前端直接给出禁用态。
 */
function isCurrentUserRow(user: SystemUserListItem): boolean {
  return authStore.currentUser?.id === user.id;
}

/**
 * 判断当前行是否存在待审批的密码申请。
 */
function hasPendingPasswordChangeRequest(user: SystemUserListItem): boolean {
  return user.passwordChangeRequestStatus === "pending";
}

/**
 * 生成人工更容易读懂的账号页密码申请摘要。
 * 这里专门把“待审批 / 已批准 / 已拒绝 / 未提交”翻译成面向用户的句子。
 */
function getCurrentPasswordRequestSummary(): string {
  if (currentPasswordRequestStatus.value === "pending") {
    return "申请已经提交，等待公司管理员审批。审批完成前，当前登录密码不会变化。";
  }
  if (currentPasswordRequestStatus.value === "approved") {
    if (currentPasswordRequestType.value === "reset_to_default") {
      return `管理员已经批准重置申请。你的临时密码已变更为 ${defaultResetPasswordLabel.value}，请尽快再次修改。`;
    }
    return "管理员已经批准新密码申请。下次登录时，请使用你申请的新密码。";
  }
  if (currentPasswordRequestStatus.value === "rejected") {
    return "上一条密码申请已被管理员拒绝。你可以检查原因后重新发起新的申请。";
  }
  return "当前还没有提交密码申请。如需改密或重置密码，可直接在这里发起站内申请。";
}

/**
 * 返回管理员申请状态的中文标签。
 */
function getAdminApplicationStatusLabel(status: CompanyApplicationFilter): string {
  if (status === "pending") {
    return "待审批";
  }
  if (status === "approved") {
    return "已通过";
  }
  if (status === "rejected") {
    return "已拒绝";
  }
  if (status === "not_applicable") {
    return "不适用";
  }
  return "全部状态";
}

/**
 * 返回管理员申请状态对应的视觉色彩。
 */
function getAdminApplicationStatusTagType(
  status: CompanyApplicationFilter,
): "warning" | "success" | "danger" | "info" {
  if (status === "pending") {
    return "warning";
  }
  if (status === "approved") {
    return "success";
  }
  if (status === "rejected") {
    return "danger";
  }
  return "info";
}

/**
 * 返回公司状态标签。
 */
function getCompanyStatusLabel(isActive: boolean): string {
  return isActive ? "运行中" : "已停用";
}

/**
 * 判断指定用户当前是否处于任一行级管理动作执行中。
 */
function isUserActionPending(userId: number): boolean {
  return updatingUserIds.value.includes(userId);
}

/**
 * 统一包裹用户表中的行级异步操作，防止同一行被重复点击。
 */
async function runUserRowAction(userId: number, action: () => Promise<void>): Promise<void> {
  if (isUserActionPending(userId)) {
    return;
  }

  updatingUserIds.value = [...updatingUserIds.value, userId];
  try {
    await action();
  } finally {
    updatingUserIds.value = updatingUserIds.value.filter((item) => item !== userId);
  }
}

/**
 * 确保右侧网关详情区始终指向一个真实存在的网关。
 * 删除、刷新或首次加载后都要做一次同步。
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
 * 清理“网关保存失败”这一类只属于弹窗本身的错误状态。
 * 列表加载错误和弹窗提交错误要分开管理，避免旧提示残留到下一次操作里。
 */
function clearGatewaySubmitError(): void {
  gatewaySubmitError.value = "";
  gatewaySubmitErrorCode.value = "";
}

/**
 * 根据网关名称在当前公司网关列表里查找现有条目。
 * 当用户提交了同名网关时，可以直接把右侧详情定位到已有条目。
 */
function findGatewayByName(name: string): AIGatewayModel | null {
  const normalizedName = name.trim();
  if (!normalizedName) {
    return null;
  }

  return gateways.value.find((item) => item.name.trim() === normalizedName) ?? null;
}

/**
 * 把网关保存异常翻译成弹窗内更易懂的说明，并保留后端错误码用于区分展示。
 */
function resolveGatewaySubmitError(
  caughtError: unknown,
): { code: string; message: string } {
  if (caughtError instanceof ApiClientError) {
    if (caughtError.code === "ai_gateway_name_exists") {
      return {
        code: caughtError.code,
        message:
          "当前公司下已经存在同名 AI 网关。若你想继续使用它，请直接编辑左侧已有网关；若要新建，请换一个名称。",
      };
    }

    if (caughtError.code === "ai_gateway_global_name_conflict") {
      return {
        code: caughtError.code,
        message:
          "数据库仍残留旧的全局唯一索引，不同公司暂时不能共用同名网关。请先确认后端已执行最新迁移，再重新刷新页面后重试。",
      };
    }

    return {
      code: caughtError.code,
      message: caughtError.message || "AI 网关保存失败",
    };
  }

  return {
    code: "unknown_error",
    message: caughtError instanceof Error ? caughtError.message : "AI 网关保存失败",
  };
}

/**
 * 如果权限变化导致当前 Tab 不再可见，就把页面安全切回基础信息页。
 */
function ensureActiveTabAllowed(): void {
  const allowedTabs: SettingsTabName[] = ["account"];

  if (isCompanyAdmin.value) {
    allowedTabs.push("company", "users", "gateways");
  }
  if (isPlatformAdmin.value) {
    allowedTabs.push("applications", "companies");
  }

  if (!allowedTabs.includes(activeTab.value)) {
    activeTab.value = "account";
  }
}

/**
 * 拉取当前登录用户的站内改密申请状态。
 * 这是账号页本地状态，不进入全局 store，避免把一次性的表单/审批信息扩散到整个应用。
 */
async function loadCurrentPasswordRequest(): Promise<void> {
  if (!authStore.currentUser) {
    passwordRequestInfo.value = null;
    return;
  }

  passwordRequestLoading.value = true;
  try {
    const response = await fetchCurrentUserPasswordChangeRequest();
    passwordRequestInfo.value = mapUserPasswordChangeRequestInfoDto(response);
  } catch (caughtError) {
    const message =
      caughtError instanceof Error ? caughtError.message : "密码申请状态加载失败";
    ElMessage.error(message);
  } finally {
    passwordRequestLoading.value = false;
  }
}

/**
 * 拉取当前登录用户所属公司的详细信息。
 * 普通公司成员也要能看到公司基础资料，因此不依赖公司管理员权限。
 */
async function loadCurrentCompany(): Promise<void> {
  if (!authStore.currentUser?.company) {
    currentCompany.value = null;
    currentCompanyError.value = "";
    return;
  }

  currentCompanyLoading.value = true;
  currentCompanyError.value = "";

  try {
    const response = await fetchCurrentCompany();
    currentCompany.value = mapCurrentCompanyResponseDto(response);
  } catch (caughtError) {
    currentCompanyError.value =
      caughtError instanceof Error ? caughtError.message : "当前公司信息加载失败";
  } finally {
    currentCompanyLoading.value = false;
  }
}

/**
 * 重置当前公司的固定邀请码。
 * 只有公司管理员才允许执行，普通成员不暴露邀请码本身。
 */
async function handleResetCurrentCompanyInviteCode(): Promise<void> {
  if (!isCompanyAdmin.value || !currentCompany.value) {
    return;
  }

  inviteCodeResetting.value = true;
  try {
    const response = await resetCurrentCompanyInviteCode();
    currentCompany.value = {
      ...currentCompany.value,
      inviteCode: response.invite_code,
    };
    ElMessage.success(response.message);
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "公司邀请码重置失败";
    ElMessage.error(message);
  } finally {
    inviteCodeResetting.value = false;
  }
}

/**
 * 拉取 AI 网关与模型配置。
 * 网关是公司级资源，因此只对公司管理员开放。
 */
async function loadGateways(): Promise<void> {
  if (!isCompanyAdmin.value) {
    gateways.value = [];
    selectedGatewayId.value = null;
    gatewayError.value = "";
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
 * 拉取当前公司下的用户列表。
 * 搜索、筛选和分页都交给后端，避免用户变多后前端一次性加载全部成员。
 */
async function loadSystemUsers(): Promise<void> {
  if (!isCompanyAdmin.value) {
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
 * 拉取平台默认管理员可见的“新公司管理员申请”列表。
 */
async function loadAdminApplications(): Promise<void> {
  if (!isPlatformAdmin.value) {
    applications.value = [];
    applicationsTotal.value = 0;
    applicationsError.value = "";
    return;
  }

  applicationsLoading.value = true;
  applicationsError.value = "";

  try {
    const response = await fetchCompanyAdminApplications({
      keyword: applicationKeyword.value.trim() || undefined,
      applicationStatus:
        applicationStatusFilter.value === "all"
          ? undefined
          : applicationStatusFilter.value,
      skip: (applicationsCurrentPage.value - 1) * applicationsPageSize.value,
      limit: applicationsPageSize.value,
    });
    applications.value = response.items.map(mapCompanyAdminApplicationItemDto);
    applicationsTotal.value = response.total;
  } catch (caughtError) {
    applicationsError.value =
      caughtError instanceof Error ? caughtError.message : "管理员申请列表加载失败";
  } finally {
    applicationsLoading.value = false;
  }
}

/**
 * 拉取平台默认管理员可见的公司列表与资源占用摘要。
 */
async function loadCompanies(): Promise<void> {
  if (!isPlatformAdmin.value) {
    companies.value = [];
    companiesTotal.value = 0;
    companiesError.value = "";
    return;
  }

  companiesLoading.value = true;
  companiesError.value = "";

  try {
    const response = await fetchCompanies({
      keyword: companyKeyword.value.trim() || undefined,
      isActive:
        companyActiveFilter.value === "all"
          ? undefined
          : companyActiveFilter.value === "active",
      skip: (companiesCurrentPage.value - 1) * companiesPageSize.value,
      limit: companiesPageSize.value,
    });
    companies.value = response.items.map(mapCompanySummaryResponseDto);
    companiesTotal.value = response.total;
  } catch (caughtError) {
    companiesError.value = caughtError instanceof Error ? caughtError.message : "公司列表加载失败";
  } finally {
    companiesLoading.value = false;
  }
}

/**
 * 根据当前权限范围批量刷新页面需要的数据。
 * 这样切换账号或角色变化时，可以一次把所有可见工作区同步到最新状态。
 */
async function loadVisibleData(): Promise<void> {
  ensureActiveTabAllowed();

  const tasks: Promise<void>[] = [];

  if (authStore.currentUser) {
    tasks.push(loadCurrentPasswordRequest());
  } else {
    passwordRequestInfo.value = null;
  }

  if (authStore.currentUser?.company) {
    tasks.push(loadCurrentCompany());
  } else {
    currentCompany.value = null;
    currentCompanyError.value = "";
  }

  if (isCompanyAdmin.value) {
    tasks.push(loadSystemUsers(), loadGateways());
  } else {
    users.value = [];
    usersTotal.value = 0;
    usersError.value = "";
    gateways.value = [];
    gatewayError.value = "";
    selectedGatewayId.value = null;
  }

  if (isPlatformAdmin.value) {
    tasks.push(loadAdminApplications(), loadCompanies());
  } else {
    applications.value = [];
    applicationsTotal.value = 0;
    applicationsError.value = "";
    companies.value = [];
    companiesTotal.value = 0;
    companiesError.value = "";
  }

  await Promise.all(tasks);
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
  clearGatewaySubmitError();
  editingGateway.value = null;
  activeGatewayPresetId.value = presetId;
  gatewayDialogVisible.value = true;
}

/**
 * 打开编辑网关弹窗。
 */
function openEditGatewayDialog(gateway: AIGatewayModel): void {
  clearGatewaySubmitError();
  editingGateway.value = gateway;
  activeGatewayPresetId.value = null;
  gatewayDialogVisible.value = true;
}

/**
 * 提交网关新增或编辑。
 * 新建成功时，会顺带把自动探测到的模型候选一起写入，减少管理员重复录入。
 */
async function handleGatewaySubmit(
  payload: AIGatewayCreateRequestDto | AIGatewayUpdateRequestDto,
  selectedCandidates: AIDiscoveredModelCandidate[],
): Promise<void> {
  clearGatewaySubmitError();
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
    const resolvedError = resolveGatewaySubmitError(caughtError);
    gatewaySubmitErrorCode.value = resolvedError.code;
    gatewaySubmitError.value = resolvedError.message;

    const duplicatedGatewayName =
      typeof payload.name === "string" ? payload.name.trim() : "";
    if (resolvedError.code === "ai_gateway_name_exists" && duplicatedGatewayName) {
      const existingGateway = findGatewayByName(duplicatedGatewayName);
      if (existingGateway) {
        selectedGatewayId.value = existingGateway.id;
      }
    }

    ElMessage.error(resolvedError.message);
  } finally {
    gatewaySubmitting.value = false;
  }
}

/**
 * 删除指定 AI 网关。
 */
async function handleDeleteGateway(gateway: AIGatewayModel): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将删除网关“${gateway.name}”及其下所有模型配置，此操作不可恢复。`,
      "删除 AI 网关",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

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
  try {
    await ElMessageBox.confirm(
      `将删除模型配置“${model.displayName}”，此操作不可恢复。`,
      "删除模型配置",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

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
 * 提交公司内用户筛选查询。
 */
async function handleUserSearch(): Promise<void> {
  usersCurrentPage.value = 1;
  await loadSystemUsers();
}

/**
 * 重置公司内用户管理筛选条件。
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
 * 切换公司内用户列表页码。
 */
async function handleUserPageChange(page: number): Promise<void> {
  usersCurrentPage.value = page;
  await loadSystemUsers();
}

/**
 * 切换公司内用户列表分页大小。
 */
async function handleUserPageSizeChange(pageSize: number): Promise<void> {
  usersPageSize.value = pageSize;
  usersCurrentPage.value = 1;
  await loadSystemUsers();
}

/**
 * 修改指定用户的 AI 使用权限。
 * 如果改的是当前登录账号，需要同步刷新 Pinia 里的本地会话快照。
 */
async function handleToggleUserAiPermission(
  user: SystemUserListItem,
  nextValue: boolean,
): Promise<void> {
  await runUserRowAction(user.id, async () => {
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
    }
  });
}

/**
 * 申请把当前账号密码重置为系统默认密码。
 */
async function handleRequestDefaultPasswordReset(): Promise<void> {
  const defaultPassword = defaultResetPasswordLabel.value;

  try {
    await ElMessageBox.confirm(
      `提交后需等待管理员批准。批准通过后，你的密码将被重置为 ${defaultPassword}。`,
      "申请重置为默认密码",
      {
        type: "warning",
        confirmButtonText: "提交申请",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  passwordRequestSubmitting.value = true;
  try {
    const response = await submitCurrentUserPasswordChangeRequest({
      request_type: "reset_to_default",
      new_password: null,
    });
    ElMessage.success(response.message);
    await loadCurrentPasswordRequest();
    if (isCompanyAdmin.value) {
      await loadSystemUsers();
    }
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "默认密码重置申请提交失败";
    ElMessage.error(message);
  } finally {
    passwordRequestSubmitting.value = false;
  }
}

/**
 * 申请把当前账号密码改成自己指定的新密码。
 */
async function handleSubmitRequestedPasswordChange(): Promise<void> {
  const nextPassword = passwordRequestForm.value.newPassword;
  const confirmPassword = passwordRequestForm.value.confirmPassword;

  if (!nextPassword.trim() || !confirmPassword.trim()) {
    ElMessage.warning("请先填写完整的新密码和确认密码。");
    return;
  }

  if (nextPassword !== confirmPassword) {
    ElMessage.warning("两次输入的新密码不一致，请重新确认。");
    return;
  }

  passwordRequestSubmitting.value = true;
  try {
    const response = await submitCurrentUserPasswordChangeRequest({
      request_type: "change_to_requested",
      new_password: nextPassword,
    });
    passwordRequestForm.value.newPassword = "";
    passwordRequestForm.value.confirmPassword = "";
    ElMessage.success(response.message);
    await loadCurrentPasswordRequest();
    if (isCompanyAdmin.value) {
      await loadSystemUsers();
    }
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "改密申请提交失败";
    ElMessage.error(message);
  } finally {
    passwordRequestSubmitting.value = false;
  }
}

/**
 * 切换指定用户的启停状态。
 */
async function handleToggleUserStatus(user: SystemUserListItem): Promise<void> {
  const nextStatus = !user.isActive;
  const actionLabel = nextStatus ? "启用" : "停用";

  try {
    await ElMessageBox.confirm(
      `确认要${actionLabel}账号“${user.displayName}”吗？`,
      `${actionLabel}用户`,
      {
        type: "warning",
        confirmButtonText: actionLabel,
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  await runUserRowAction(user.id, async () => {
    try {
      await updateSystemUserStatus(user.id, {
        is_active: nextStatus,
      });

      if (authStore.currentUser?.id === user.id) {
        authStore.currentUser = {
          ...authStore.currentUser,
          isActive: nextStatus,
        };
      }

      ElMessage.success(nextStatus ? "该用户已启用" : "该用户已停用");
      await loadSystemUsers();
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "用户状态更新失败";
      ElMessage.error(message);
    }
  });
}

/**
 * 删除指定用户账号。
 */
async function handleDeleteUser(user: SystemUserListItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `删除后将无法恢复，确认要删除账号“${user.displayName}”吗？`,
      "删除用户",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  await runUserRowAction(user.id, async () => {
    try {
      const response = await deleteSystemUser(user.id);
      ElMessage.success(response.message);
      await loadSystemUsers();
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "删除用户失败";
      ElMessage.error(message);
    }
  });
}

/**
 * 批准指定用户的站内改密申请。
 */
async function handleApproveUserPasswordRequest(user: SystemUserListItem): Promise<void> {
  const requestTypeLabel = getPasswordRequestTypeLabel(user.passwordChangeRequestType);

  try {
    await ElMessageBox.confirm(
      `确认要批准“${user.displayName}”的${requestTypeLabel}申请吗？`,
      "批准密码申请",
      {
        type: "warning",
        confirmButtonText: "批准",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  await runUserRowAction(user.id, async () => {
    try {
      const response = await approveSystemUserPasswordChangeRequest(user.id);
      if (response.applied_password) {
        ElMessage.success(`${response.message} 默认密码为：${response.applied_password}`);
      } else {
        ElMessage.success(response.message);
      }
      await loadSystemUsers();
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "批准密码申请失败";
      ElMessage.error(message);
    }
  });
}

/**
 * 拒绝指定用户的站内改密申请。
 */
async function handleRejectUserPasswordRequest(user: SystemUserListItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认要拒绝“${user.displayName}”的密码申请吗？`,
      "拒绝密码申请",
      {
        type: "warning",
        confirmButtonText: "拒绝",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  await runUserRowAction(user.id, async () => {
    try {
      const response = await rejectSystemUserPasswordChangeRequest(user.id);
      ElMessage.success(response.message);
      await loadSystemUsers();
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "拒绝密码申请失败";
      ElMessage.error(message);
    }
  });
}

/**
 * 提交平台审批列表筛选。
 */
async function handleApplicationSearch(): Promise<void> {
  applicationsCurrentPage.value = 1;
  await loadAdminApplications();
}

/**
 * 重置平台审批列表筛选条件。
 */
async function handleResetApplicationFilters(): Promise<void> {
  applicationKeyword.value = "";
  applicationStatusFilter.value = "pending";
  applicationsCurrentPage.value = 1;
  await loadAdminApplications();
}

/**
 * 切换平台审批列表页码。
 */
async function handleApplicationPageChange(page: number): Promise<void> {
  applicationsCurrentPage.value = page;
  await loadAdminApplications();
}

/**
 * 切换平台审批列表分页大小。
 */
async function handleApplicationPageSizeChange(pageSize: number): Promise<void> {
  applicationsPageSize.value = pageSize;
  applicationsCurrentPage.value = 1;
  await loadAdminApplications();
}

/**
 * 批准指定新公司管理员申请，并自动创建公司。
 * 审批通过后，公司列表也需要同步刷新，避免计数和状态落后。
 */
async function handleApproveApplication(application: CompanyAdminApplicationItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将批准账号“${application.username}”的申请，并自动创建公司“${application.requestedCompanyName ?? "未命名公司"}”。`,
      "批准管理员申请",
      {
        type: "warning",
        confirmButtonText: "批准",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  try {
    await approveCompanyAdminApplication(application.id);
    ElMessage.success("管理员申请已批准，并已自动创建公司");
    await Promise.all([loadAdminApplications(), loadCompanies()]);
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "批准管理员申请失败";
    ElMessage.error(message);
  }
}

/**
 * 拒绝指定新公司管理员申请。
 */
async function handleRejectApplication(application: CompanyAdminApplicationItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `将拒绝账号“${application.username}”的管理员申请。该账号不会获得新公司管理权限。`,
      "拒绝管理员申请",
      {
        type: "warning",
        confirmButtonText: "拒绝",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  try {
    await rejectCompanyAdminApplication(application.id);
    ElMessage.success("管理员申请已拒绝");
    await loadAdminApplications();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "拒绝管理员申请失败";
    ElMessage.error(message);
  }
}

/**
 * 提交平台公司列表筛选。
 */
async function handleCompanySearch(): Promise<void> {
  companiesCurrentPage.value = 1;
  await loadCompanies();
}

/**
 * 重置平台公司列表筛选条件。
 */
async function handleResetCompanyFilters(): Promise<void> {
  companyKeyword.value = "";
  companyActiveFilter.value = "all";
  companiesCurrentPage.value = 1;
  await loadCompanies();
}

/**
 * 切换平台公司列表页码。
 */
async function handleCompanyPageChange(page: number): Promise<void> {
  companiesCurrentPage.value = page;
  await loadCompanies();
}

/**
 * 切换平台公司列表分页大小。
 */
async function handleCompanyPageSizeChange(pageSize: number): Promise<void> {
  companiesPageSize.value = pageSize;
  companiesCurrentPage.value = 1;
  await loadCompanies();
}

/**
 * 停用指定公司。
 * 停用后该公司的成员无法继续登录和使用业务功能，但数据仍保留待二次确认删除。
 */
async function handleDeactivateCompany(company: CompanySummary): Promise<void> {
  if (company.isSystemReserved) {
    ElMessage.warning("系统保留公司不允许停用。");
    return;
  }
  if (!company.isActive) {
    ElMessage.info("该公司已经是停用状态。");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `将停用公司“${company.name}”。停用后，该公司成员将无法继续登录系统。`,
      "停用公司",
      {
        type: "warning",
        confirmButtonText: "停用",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  try {
    await deactivateCompany(company.id);
    ElMessage.success("公司已停用");
    await loadCompanies();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "停用公司失败";
    ElMessage.error(message);
  }
}

/**
 * 彻底删除公司。
 * 这里要求操作者再次输入公司名，减少误删风险。
 */
async function handlePurgeCompany(company: CompanySummary): Promise<void> {
  if (company.isSystemReserved) {
    ElMessage.warning("系统保留公司不允许彻底删除。");
    return;
  }
  if (company.isActive) {
    ElMessage.warning("请先停用公司，再执行彻底删除。");
    return;
  }

  let value = "";
  try {
    const promptResult = await ElMessageBox.prompt(
      `请输入公司名称“${company.name}”确认彻底删除。删除会同时清理该公司用户、业务数据和对象存储占用。`,
      "彻底删除公司",
      {
        type: "warning",
        confirmButtonText: "彻底删除",
        cancelButtonText: "取消",
        inputPlaceholder: `请输入 ${company.name}`,
        inputErrorMessage: "请输入公司名称后再继续。",
        inputPattern: /.+/,
      },
    );
    value = promptResult.value;
  } catch {
    return;
  }

  try {
    await purgeCompany(company.id, {
      confirm_name: value.trim(),
    });
    ElMessage.success("公司已彻底删除");
    await loadCompanies();
  } catch (caughtError) {
    const message = caughtError instanceof Error ? caughtError.message : "彻底删除公司失败";
    ElMessage.error(message);
  }
}

/**
 * 返回模型最终会使用的 Base URL。
 * 没有独立覆盖地址时，模型沿用所属网关的基础地址。
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
  () =>
    `${authStore.currentUser?.company?.id ?? "none"}:${isCompanyAdmin.value}:${isPlatformAdmin.value}`,
  () => {
    void loadVisibleData();
  },
  { immediate: true },
);

/**
 * 弹窗关闭时立即清理提交错误，避免下次再打开还看到上一轮失败提示。
 */
watch(gatewayDialogVisible, (visible) => {
  if (!visible) {
    clearGatewaySubmitError();
  }
});
</script>

<template>
  <div class="page-grid settings-page">
    <PageHeader
      eyebrow="Settings"
      title="系统设置"
      description="这个页面现在按多租户角色拆成三层：所有用户都能看自己的账号与公司基础信息；公司管理员额外管理邀请码、公司成员和本公司 AI 网关；平台默认管理员再管理新公司审批与公司空间回收。"
    />

    <ElTabs v-model="activeTab" class="settings-tabs">
      <ElTabPane label="基础信息" name="account">
        <section class="app-panel settings-panel" v-loading="currentCompanyLoading">
          <div class="settings-panel__header">
            <div>
              <strong>当前账号</strong>
              <p class="muted-text">
                用户端可以在这里确认账号状态、所属公司、AI 分析权限和管理员身份层级。
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
              <ElTag :type="canUseAiAnalysis ? 'success' : 'warning'" effect="dark" round>
                {{ canUseAiAnalysis ? "AI 分析已授权" : "AI 分析未授权" }}
              </ElTag>
              <ElTag :type="isPlatformAdmin ? 'success' : 'info'" effect="plain" round>
                {{ isPlatformAdmin ? "平台默认管理员" : isCompanyAdmin ? "公司管理员" : "普通成员" }}
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
              <span class="account-summary-card__label">所属公司</span>
              <strong>{{ companyDisplayName }}</strong>
              <p class="muted-text">当前账号能看到的数据、设备和 AI 配置都归属于这家公司。</p>
            </article>
            <article class="account-summary-card">
              <span class="account-summary-card__label">AI 权限</span>
              <strong>{{ canUseAiAnalysis ? "已开通" : "未开通" }}</strong>
              <p class="muted-text">AI 分析权限由公司管理员单独授权，不会默认开启。</p>
            </article>
            <article class="account-summary-card">
              <span class="account-summary-card__label">管理员状态</span>
              <strong>
                {{
                  isPlatformAdmin
                    ? "平台默认管理员"
                    : isCompanyAdmin
                      ? getAdminApplicationStatusLabel(
                        authStore.currentUser?.adminApplicationStatus ?? "not_applicable"
                      )
                      : "普通成员"
                }}
              </strong>
              <p class="muted-text">
                平台默认管理员可审批新公司，普通公司管理员只管理本公司资源。
              </p>
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
            <ElDescriptionsItem label="所属公司">
              {{ companyDisplayName }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="公司状态">
              {{ currentCompany ? getCompanyStatusLabel(currentCompany.isActive) : "未获取" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="平台默认管理员">
              {{ isPlatformAdmin ? "是" : "否" }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="管理员申请状态">
              {{ getAdminApplicationStatusLabel(authStore.currentUser?.adminApplicationStatus ?? "not_applicable") }}
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
            <ElDescriptionsItem label="账号创建时间">
              {{ formatDateTime(authStore.currentUser?.createdAt ?? null) }}
            </ElDescriptionsItem>
          </ElDescriptions>

          <ElAlert
            v-if="currentCompanyError"
            type="warning"
            show-icon
            :closable="false"
            :title="currentCompanyError"
          />

          <section class="password-request-panel" v-loading="passwordRequestLoading">
            <div class="settings-panel__header">
              <div>
                <strong>站内密码申请</strong>
                <p class="muted-text">
                  不再依赖邮箱链路。你可以在这里申请“重置为默认密码”或“改成指定新密码”，由公司管理员审批后生效。
                </p>
              </div>
              <div class="settings-panel__status-tags">
                <ElTag
                  :type="getPasswordRequestTagType(currentPasswordRequestStatus)"
                  effect="dark"
                  round
                >
                  {{ getPasswordRequestStatusLabel(currentPasswordRequestStatus) }}
                </ElTag>
                <ElTag effect="plain" round>
                  {{ getPasswordRequestTypeLabel(currentPasswordRequestType) }}
                </ElTag>
              </div>
            </div>

            <div class="password-request-grid">
              <article class="password-request-card password-request-card--summary">
                <div class="table-stack">
                  <strong>当前申请摘要</strong>
                  <span>{{ getCurrentPasswordRequestSummary() }}</span>
                  <span>
                    最近提交时间：{{ formatDateTime(passwordRequestInfo?.passwordChangeRequestedAt ?? null) }}
                  </span>
                  <span>
                    最近审批时间：{{ formatDateTime(passwordRequestInfo?.passwordChangeReviewedAt ?? null) }}
                  </span>
                </div>

                <ElAlert
                  type="info"
                  show-icon
                  :closable="false"
                  :title="`默认重置密码固定为 ${defaultResetPasswordLabel}`"
                  description="当你选择“重置为默认密码”且管理员批准后，系统会把密码改成这个临时密码。登录后请尽快再次修改。"
                />
              </article>

              <article class="password-request-card">
                <div class="table-stack">
                  <strong>申请重置为默认密码</strong>
                  <span>适用于忘记当前密码、需要管理员快速恢复登录的场景。</span>
                  <span>审批通过后，密码会被重置为 {{ defaultResetPasswordLabel }}。</span>
                </div>

                <ElButton
                  type="warning"
                  :loading="passwordRequestSubmitting"
                  :disabled="isCurrentPasswordRequestPending"
                  @click="handleRequestDefaultPasswordReset"
                >
                  {{ isCurrentPasswordRequestPending ? "已有待审批申请" : "申请重置为默认密码" }}
                </ElButton>
              </article>

              <article class="password-request-card">
                <div class="table-stack">
                  <strong>申请修改为指定新密码</strong>
                  <span>提交你希望生效的新密码，管理员审批通过后，系统会直接把账号密码改成该值。</span>
                </div>

                <div class="password-request-form">
                  <ElInput
                    v-model="passwordRequestForm.newPassword"
                    type="password"
                    show-password
                    placeholder="请输入希望审批后生效的新密码"
                    :disabled="isCurrentPasswordRequestPending || passwordRequestSubmitting"
                  />
                  <ElInput
                    v-model="passwordRequestForm.confirmPassword"
                    type="password"
                    show-password
                    placeholder="请再次输入新密码"
                    :disabled="isCurrentPasswordRequestPending || passwordRequestSubmitting"
                    @keyup.enter="handleSubmitRequestedPasswordChange"
                  />
                  <ElButton
                    type="primary"
                    :loading="passwordRequestSubmitting"
                    :disabled="isCurrentPasswordRequestPending"
                    @click="handleSubmitRequestedPasswordChange"
                  >
                    {{ isCurrentPasswordRequestPending ? "已有待审批申请" : "申请修改为新密码" }}
                  </ElButton>
                </div>
              </article>
            </div>
          </section>
        </section>
      </ElTabPane>

      <ElTabPane v-if="isCompanyAdmin" label="公司设置" name="company">
        <section class="app-panel settings-panel" v-loading="currentCompanyLoading">
          <div class="settings-panel__header">
            <div>
              <strong>当前公司与邀请码</strong>
              <p class="muted-text">
                当前公司采用固定邀请码模式。普通用户注册时输入邀请码即可直接加入本公司，无需再次审批。
              </p>
            </div>
            <div class="settings-panel__actions">
              <ElButton @click="loadCurrentCompany" :loading="currentCompanyLoading">刷新</ElButton>
              <ElButton
                type="primary"
                @click="handleResetCurrentCompanyInviteCode"
                :loading="inviteCodeResetting"
                :disabled="!currentCompany || !currentCompany.isActive"
              >
                重置邀请码
              </ElButton>
            </div>
          </div>

          <ElAlert
            v-if="currentCompanyError"
            type="error"
            show-icon
            :closable="false"
            :title="currentCompanyError"
          />

          <template v-if="currentCompany">
            <div class="company-overview">
              <article class="account-summary-card">
                <span class="account-summary-card__label">公司名称</span>
                <strong>{{ currentCompany.name }}</strong>
                <p class="muted-text">当前登录账号所属的业务空间名称。</p>
              </article>
              <article class="account-summary-card">
                <span class="account-summary-card__label">固定邀请码</span>
                <strong class="mono-text">{{ currentCompany.inviteCode }}</strong>
                <p class="muted-text">发给普通成员后，可直接用于注册加入本公司。</p>
              </article>
              <article class="account-summary-card">
                <span class="account-summary-card__label">空间类型</span>
                <strong>{{ currentCompany.isSystemReserved ? "系统保留公司" : "普通公司空间" }}</strong>
                <p class="muted-text">
                  系统保留公司不会被平台默认管理员停用或彻底删除。
                </p>
              </article>
            </div>

            <ElDescriptions :column="2" border>
              <ElDescriptionsItem label="公司名称">
                {{ currentCompany.name }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="公司状态">
                {{ getCompanyStatusLabel(currentCompany.isActive) }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="联系人">
                {{ currentCompany.contactName ?? "未填写" }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="邀请码">
                <span class="mono-text">{{ currentCompany.inviteCode }}</span>
              </ElDescriptionsItem>
              <ElDescriptionsItem label="备注" :span="2">
                {{ currentCompany.note ?? "未填写" }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="创建时间">
                {{ formatDateTime(currentCompany.createdAt) }}
              </ElDescriptionsItem>
              <ElDescriptionsItem label="更新时间">
                {{ formatDateTime(currentCompany.updatedAt) }}
              </ElDescriptionsItem>
            </ElDescriptions>

            <ElAlert
              :type="currentCompany.isSystemReserved ? 'info' : 'success'"
              show-icon
              :closable="false"
              :title="currentCompany.isSystemReserved ? '当前是系统保留公司' : '当前公司使用固定邀请码入司策略'"
              :description="
                currentCompany.isSystemReserved
                  ? '这个公司主要承载平台默认管理员和历史迁移数据，不参与普通公司停用与彻底删除流程。'
                  : '你可以把上面的固定邀请码发给成员。成员注册成功后会直接加入本公司，后续 AI 权限再由你在“用户管理”里单独开启。'
              "
            />
          </template>
        </section>
      </ElTabPane>

      <ElTabPane v-if="isCompanyAdmin" label="用户管理" name="users">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>{{ companyDisplayName }} 成员管理</strong>
              <p class="muted-text">
                新注册用户默认不开放 AI 分析。公司管理员可以按搜索、角色、状态和 AI 授权状态筛选本公司成员，再决定是否放开 AI。
              </p>
            </div>
            <div class="settings-panel__actions">
              <ElButton @click="loadSystemUsers" :loading="usersLoading">刷新</ElButton>
            </div>
          </div>

          <div class="filter-grid filter-grid--users">
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

            <div class="filter-grid__actions">
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
                <div class="table-stack">
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
                  :loading="isUserActionPending(row.id)"
                  @change="(value) => handleToggleUserAiPermission(row, Boolean(value))"
                />
              </template>
            </ElTableColumn>
            <ElTableColumn label="密码申请" min-width="250">
              <template #default="{ row }">
                <div class="table-stack">
                  <div class="table-tags">
                    <ElTag
                      :type="getPasswordRequestTagType(row.passwordChangeRequestStatus)"
                      effect="dark"
                      round
                    >
                      {{ getPasswordRequestStatusLabel(row.passwordChangeRequestStatus) }}
                    </ElTag>
                    <ElTag effect="plain" round>
                      {{ getPasswordRequestTypeLabel(row.passwordChangeRequestType) }}
                    </ElTag>
                    <ElTag v-if="isCurrentUserRow(row)" type="info" effect="plain" round>
                      当前账号
                    </ElTag>
                  </div>
                  <span>
                    申请时间：{{ formatDateTime(row.passwordChangeRequestedAt) }}
                  </span>
                  <span>
                    审批时间：{{ formatDateTime(row.passwordChangeReviewedAt) }}
                  </span>
                </div>
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
            <ElTableColumn label="操作" min-width="260">
              <template #default="{ row }">
                <div class="table-actions">
                  <ElButton
                    v-if="hasPendingPasswordChangeRequest(row)"
                    text
                    type="primary"
                    :disabled="isCurrentUserRow(row) || isUserActionPending(row.id)"
                    @click="handleApproveUserPasswordRequest(row)"
                  >
                    批准
                  </ElButton>
                  <ElButton
                    v-if="hasPendingPasswordChangeRequest(row)"
                    text
                    type="warning"
                    :disabled="isCurrentUserRow(row) || isUserActionPending(row.id)"
                    @click="handleRejectUserPasswordRequest(row)"
                  >
                    拒绝
                  </ElButton>
                  <ElButton
                    text
                    :disabled="isCurrentUserRow(row) || isUserActionPending(row.id)"
                    @click="handleToggleUserStatus(row)"
                  >
                    {{ row.isActive ? "停用" : "启用" }}
                  </ElButton>
                  <ElButton
                    text
                    type="danger"
                    :disabled="isCurrentUserRow(row) || isUserActionPending(row.id)"
                    @click="handleDeleteUser(row)"
                  >
                    删除
                  </ElButton>
                </div>
              </template>
            </ElTableColumn>
          </ElTable>

          <div class="settings-pagination">
            <span class="muted-text">
              共 {{ usersTotal }} 个成员，当前第 {{ usersCurrentPage }} / {{ usersPageCount }} 页
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

      <ElTabPane v-if="isPlatformAdmin" label="平台审批" name="applications">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>新公司管理员申请审批</strong>
              <p class="muted-text">
                只有平台默认管理员可以批准“新公司管理员申请”。批准后系统会自动创建新公司，并把申请人升级为该公司的最高管理员。
              </p>
            </div>
            <div class="settings-panel__actions">
              <ElButton @click="loadAdminApplications" :loading="applicationsLoading">刷新</ElButton>
            </div>
          </div>

          <div class="filter-grid">
            <ElInput
              v-model="applicationKeyword"
              clearable
              placeholder="搜索账号、邮箱或申请公司"
              @keyup.enter="handleApplicationSearch"
            />

            <ElSelect v-model="applicationStatusFilter" placeholder="审批状态">
              <ElOption label="全部状态" value="all" />
              <ElOption label="待审批" value="pending" />
              <ElOption label="已通过" value="approved" />
              <ElOption label="已拒绝" value="rejected" />
            </ElSelect>

            <div class="filter-grid__actions">
              <ElButton type="primary" :loading="applicationsLoading" @click="handleApplicationSearch">
                查询
              </ElButton>
              <ElButton plain @click="handleResetApplicationFilters">重置</ElButton>
            </div>
          </div>

          <ElAlert
            v-if="applicationsError"
            type="error"
            show-icon
            :closable="false"
            :title="applicationsError"
          />

          <ElTable
            :data="applications"
            v-loading="applicationsLoading"
            empty-text="当前筛选条件下没有管理员申请"
            class="settings-table"
          >
            <ElTableColumn label="申请账号" min-width="220">
              <template #default="{ row }">
                <div class="table-stack">
                  <strong>{{ row.displayName }}</strong>
                  <span>{{ row.username }}</span>
                  <span>{{ row.email ?? "未填写邮箱" }}</span>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="申请公司" min-width="220">
              <template #default="{ row }">
                <div class="table-stack">
                  <strong>{{ row.requestedCompanyName ?? "未填写" }}</strong>
                  <span>联系人：{{ row.requestedCompanyContactName ?? "未填写" }}</span>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="审批状态" min-width="120">
              <template #default="{ row }">
                <ElTag
                  :type="getAdminApplicationStatusTagType(row.adminApplicationStatus)"
                  effect="dark"
                  round
                >
                  {{ getAdminApplicationStatusLabel(row.adminApplicationStatus) }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="申请备注" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.requestedCompanyNote ?? "未填写" }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="提交时间" min-width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.createdAt) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" min-width="180">
              <template #default="{ row }">
                <div class="table-actions">
                  <template v-if="row.adminApplicationStatus === 'pending'">
                    <ElButton text type="primary" @click="handleApproveApplication(row)">
                      批准
                    </ElButton>
                    <ElButton text type="danger" @click="handleRejectApplication(row)">
                      拒绝
                    </ElButton>
                  </template>
                  <span v-else class="muted-text">已处理</span>
                </div>
              </template>
            </ElTableColumn>
          </ElTable>

          <div class="settings-pagination">
            <span class="muted-text">
              共 {{ applicationsTotal }} 条申请，当前第 {{ applicationsCurrentPage }} / {{ applicationsPageCount }} 页
            </span>

            <ElPagination
              background
              layout="prev, pager, next, sizes, total"
              :current-page="applicationsCurrentPage"
              :page-size="applicationsPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="applicationsTotal"
              @current-change="handleApplicationPageChange"
              @size-change="handleApplicationPageSizeChange"
            />
          </div>
        </section>
      </ElTabPane>

      <ElTabPane v-if="isPlatformAdmin" label="公司管理" name="companies">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>公司空间管理</strong>
              <p class="muted-text">
                平台默认管理员可以查看所有公司、停用公司，并在二次确认后彻底删除整个公司空间。彻底删除会同步清理该公司的成员、业务数据和对象存储占用。
              </p>
            </div>
            <div class="settings-panel__actions">
              <ElButton @click="loadCompanies" :loading="companiesLoading">刷新</ElButton>
            </div>
          </div>

          <div class="filter-grid">
            <ElInput
              v-model="companyKeyword"
              clearable
              placeholder="搜索公司名称或联系人"
              @keyup.enter="handleCompanySearch"
            />

            <ElSelect v-model="companyActiveFilter" placeholder="公司状态">
              <ElOption label="全部状态" value="all" />
              <ElOption label="运行中" value="active" />
              <ElOption label="已停用" value="inactive" />
            </ElSelect>

            <div class="filter-grid__actions">
              <ElButton type="primary" :loading="companiesLoading" @click="handleCompanySearch">
                查询
              </ElButton>
              <ElButton plain @click="handleResetCompanyFilters">重置</ElButton>
            </div>
          </div>

          <ElAlert
            v-if="companiesError"
            type="error"
            show-icon
            :closable="false"
            :title="companiesError"
          />

          <ElTable
            :data="companies"
            v-loading="companiesLoading"
            empty-text="当前筛选条件下没有公司"
            class="settings-table"
          >
            <ElTableColumn label="公司信息" min-width="260">
              <template #default="{ row }">
                <div class="table-stack">
                  <strong>{{ row.name }}</strong>
                  <span>联系人：{{ row.contactName ?? "未填写" }}</span>
                  <span>{{ row.note ?? "未填写备注" }}</span>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="状态" min-width="170">
              <template #default="{ row }">
                <div class="table-tags">
                  <ElTag :type="row.isActive ? 'success' : 'info'" effect="dark" round>
                    {{ getCompanyStatusLabel(row.isActive) }}
                  </ElTag>
                  <ElTag v-if="row.isSystemReserved" effect="plain" round>
                    系统保留
                  </ElTag>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="邀请码" min-width="160">
              <template #default="{ row }">
                <span class="mono-text">{{ row.inviteCode }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn label="资源占用" min-width="240">
              <template #default="{ row }">
                <div class="table-metrics">
                  <span>用户 {{ row.userCount }}</span>
                  <span>零件 {{ row.partCount }}</span>
                  <span>设备 {{ row.deviceCount }}</span>
                  <span>记录 {{ row.recordCount }}</span>
                  <span>网关 {{ row.gatewayCount }}</span>
                </div>
              </template>
            </ElTableColumn>
            <ElTableColumn label="更新时间" min-width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.updatedAt) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" min-width="220">
              <template #default="{ row }">
                <div class="table-actions">
                  <ElButton
                    text
                    :disabled="row.isSystemReserved || !row.isActive"
                    @click="handleDeactivateCompany(row)"
                  >
                    停用
                  </ElButton>
                  <ElButton
                    text
                    type="danger"
                    :disabled="row.isSystemReserved || row.isActive"
                    @click="handlePurgeCompany(row)"
                  >
                    彻底删除
                  </ElButton>
                </div>
              </template>
            </ElTableColumn>
          </ElTable>

          <div class="settings-pagination">
            <span class="muted-text">
              共 {{ companiesTotal }} 家公司，当前第 {{ companiesCurrentPage }} / {{ companiesPageCount }} 页
            </span>

            <ElPagination
              background
              layout="prev, pager, next, sizes, total"
              :current-page="companiesCurrentPage"
              :page-size="companiesPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="companiesTotal"
              @current-change="handleCompanyPageChange"
              @size-change="handleCompanyPageSizeChange"
            />
          </div>
        </section>
      </ElTabPane>

      <ElTabPane v-if="isCompanyAdmin" label="AI 网关" name="gateways">
        <section class="app-panel settings-panel">
          <div class="settings-panel__header">
            <div>
              <strong>{{ companyDisplayName }} 的 AI 网关与模型配置</strong>
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
              <div class="gateway-preset-card__header">
                <div class="gateway-preset-card__title-group">
                  <strong>{{ preset.title }}</strong>
                  <span class="gateway-preset-card__alias">{{ preset.payload.name }}</span>
                </div>
                <div class="gateway-preset-card__tags">
                  <ElTag effect="plain" round>
                    {{ gatewayVendorLabels[preset.payload.vendor] }}
                  </ElTag>
                  <ElTag
                    effect="plain"
                    round
                    :type="preset.payload.is_custom ? 'warning' : 'success'"
                  >
                    {{ preset.payload.is_custom ? "自定义" : "官方预设" }}
                  </ElTag>
                </div>
              </div>

              <div class="gateway-preset-card__body">
                <p class="gateway-preset-card__summary">{{ preset.summary }}</p>

                <div class="gateway-preset-card__meta">
                  <div class="gateway-preset-card__meta-item">
                    <span class="gateway-preset-card__meta-label">基础地址</span>
                    <strong class="gateway-preset-card__meta-value mono-text">
                      {{ preset.payload.base_url || "创建时填写" }}
                    </strong>
                  </div>
                  <div class="gateway-preset-card__meta-item">
                    <span class="gateway-preset-card__meta-label">接入说明</span>
                    <p class="gateway-preset-card__note">
                      {{ preset.payload.note || "按实际供应商文档补充协议说明。" }}
                    </p>
                  </div>
                </div>
              </div>

              <div class="gateway-preset-card__footer">
                <span class="muted-text">
                  {{ preset.payload.official_url ? "已附带官方文档地址" : "需要自行补充文档地址" }}
                </span>
                <div class="gateway-preset-card__footer-actions">
                  <ElLink
                    v-if="preset.payload.official_url"
                    type="primary"
                    :href="preset.payload.official_url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看文档
                  </ElLink>
                  <ElButton type="primary" plain @click="openCreateGatewayDialog(preset.id)">
                    用此预设新建
                  </ElButton>
                </div>
              </div>
            </article>
          </div>

          <div class="gateway-workspace">
            <aside class="gateway-list">
              <div class="gateway-list__header">
                <strong>网关列表</strong>
                <span class="muted-text">共 {{ gateways.length }} 个</span>
              </div>

              <div v-if="gateways.length > 0" class="gateway-list__overview">
                <div class="gateway-list__metric">
                  <span class="gateway-list__metric-label">已启用</span>
                  <strong>{{ enabledGatewayCount }}</strong>
                </div>
                <div class="gateway-list__metric">
                  <span class="gateway-list__metric-label">当前模型</span>
                  <strong>{{ activeGatewayModelCount }}</strong>
                </div>
              </div>

              <p v-if="gateways.length > 0" class="gateway-list__hint">
                左侧只看网关摘要，右侧再展开基础配置、密钥状态和模型明细，避免整页堆满信息。
              </p>

              <div v-if="gateways.length === 0" class="gateway-list__empty">
                <ElEmpty description="还没有 AI 网关配置" />
              </div>

              <div v-if="gateways.length > 0" class="gateway-list__items">
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
              </div>
            </aside>

            <section class="gateway-detail">
              <template v-if="activeGateway">
                <div class="gateway-detail__header">
                  <div>
                    <strong>{{ activeGateway.name }}</strong>
                    <p class="muted-text">
                      右侧只展开当前选中的网关详情和模型列表，避免所有网关模型一股脑全部摊开。
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
                        同一网关下可以挂多个模型配置，但详情区只显示当前网关，并对模型列表做分页，避免长表把整个页面拖得过长。
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

                  <div v-if="activeGatewayModels.length > 0" class="gateway-detail__model-metrics">
                    <article class="gateway-detail__model-metric">
                      <span class="gateway-detail__model-metric-label">模型总数</span>
                      <strong>{{ activeGatewayModels.length }}</strong>
                    </article>
                    <article class="gateway-detail__model-metric">
                      <span class="gateway-detail__model-metric-label">已启用</span>
                      <strong>{{ activeGatewayEnabledModelCount }}</strong>
                    </article>
                    <article class="gateway-detail__model-metric">
                      <span class="gateway-detail__model-metric-label">支持视觉</span>
                      <strong>{{ activeGatewayVisionModelCount }}</strong>
                    </article>
                    <article class="gateway-detail__model-metric">
                      <span class="gateway-detail__model-metric-label">支持流式</span>
                      <strong>{{ activeGatewayStreamingModelCount }}</strong>
                    </article>
                  </div>

                  <ElTable
                    :data="pagedActiveGatewayModels"
                    empty-text="当前网关还没有配置模型"
                    class="settings-table"
                  >
                    <ElTableColumn prop="displayName" label="显示名" min-width="170" />
                    <ElTableColumn label="模型品牌" min-width="120">
                      <template #default="{ row }">
                        {{ getModelVendorLabel(row.upstreamVendor) }}
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="接入方式" min-width="200">
                      <template #default="{ row }">
                        <div class="table-stack">
                          <strong>{{ getProtocolLabel(row.protocolType) }}</strong>
                          <span>鉴权：{{ getAuthModeLabel(row.authMode) }}</span>
                        </div>
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="接入配置" min-width="280" show-overflow-tooltip>
                      <template #default="{ row }">
                        <div class="table-stack">
                          <strong class="mono-text">{{ row.modelIdentifier }}</strong>
                          <span>{{ resolveModelBaseUrl(activeGateway, row) }}</span>
                        </div>
                      </template>
                    </ElTableColumn>
                    <ElTableColumn label="能力" min-width="140">
                      <template #default="{ row }">
                        <div class="table-tags">
                          <ElTag
                            size="small"
                            :type="row.supportsVision ? 'success' : 'info'"
                            effect="plain"
                            round
                          >
                            {{ row.supportsVision ? "视觉" : "文本" }}
                          </ElTag>
                          <ElTag
                            size="small"
                            :type="row.supportsStream ? 'primary' : 'info'"
                            effect="plain"
                            round
                          >
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

                  <div
                    v-if="activeGatewayModels.length > 0"
                    class="settings-pagination gateway-detail__model-pagination"
                  >
                    <span class="muted-text">
                      共 {{ activeGatewayModels.length }} 个模型，当前第
                      {{ normalizedGatewayModelCurrentPage }} / {{ gatewayModelPageCount }} 页
                    </span>

                    <ElPagination
                      background
                      layout="prev, pager, next, sizes, total"
                      :current-page="normalizedGatewayModelCurrentPage"
                      :page-size="gatewayModelPageSize"
                      :page-sizes="[6, 10, 20]"
                      :total="activeGatewayModels.length"
                      @current-change="handleGatewayModelPageChange"
                      @size-change="handleGatewayModelPageSizeChange"
                    />
                  </div>
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
      :submit-error="gatewaySubmitError"
      :submit-error-code="gatewaySubmitErrorCode"
      @clear-submit-error="clearGatewaySubmitError"
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
.gateway-preset-card,
.password-request-panel,
.password-request-card,
.password-request-form {
  display: grid;
  gap: 16px;
}

.settings-panel {
  padding: 22px;
  align-content: start;
}

.settings-page {
  align-content: start;
}

.settings-panel__header,
.settings-panel__actions,
.settings-panel__status-tags,
.gateway-detail__header,
.settings-pagination,
.table-actions,
.table-tags,
.gateway-summary__head,
.gateway-summary__tags,
.filter-grid__actions {
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
.table-tags,
.gateway-summary__tags,
.filter-grid__actions {
  flex-wrap: wrap;
}

.settings-tabs {
  display: grid;
  gap: 18px;
  align-content: start;
}

.settings-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.settings-tabs :deep(.el-tabs__nav-wrap::after) {
  background: rgba(149, 184, 223, 0.1);
}

.settings-tabs :deep(.el-tabs__nav) {
  padding: 6px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(8, 20, 33, 0.78);
}

.settings-tabs :deep(.el-tabs__item) {
  height: auto;
  line-height: 1.4;
  padding: 12px 18px;
  border-radius: 12px;
  color: var(--app-text-secondary);
}

.settings-tabs :deep(.el-tabs__item.is-active) {
  color: #eef5fc;
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.16), transparent 44%),
    rgba(255, 255, 255, 0.05);
}

.settings-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

.settings-tabs :deep(.el-tabs__content),
.settings-tabs :deep(.el-tab-pane) {
  display: grid;
  gap: 18px;
  padding-top: 6px;
  align-content: start;
}

.settings-tabs :deep(.el-tabs__content) {
  padding-right: 6px;
}

.account-overview,
.company-overview,
.gateway-preset-grid,
.gateway-workspace,
.filter-grid,
.password-request-grid {
  display: grid;
  gap: 16px;
}

.account-overview,
.company-overview {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.account-summary-card {
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.1), transparent 34%),
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

.filter-grid {
  grid-template-columns: minmax(240px, 1.4fr) minmax(180px, 1fr) auto;
  align-items: center;
}

.filter-grid--users {
  grid-template-columns: minmax(240px, 1.4fr) repeat(3, minmax(180px, 1fr)) auto;
}

.password-request-grid {
  grid-template-columns: minmax(280px, 1.1fr) repeat(2, minmax(0, 1fr));
}

.password-request-panel {
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.1), transparent 34%),
    rgba(255, 255, 255, 0.02);
}

.password-request-card {
  min-width: 0;
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.02);
}

.password-request-card--summary {
  align-content: start;
}

.password-request-form {
  align-content: start;
}

.settings-table {
  width: 100%;
}

.table-stack {
  display: grid;
  gap: 6px;
}

.table-stack span {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.table-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-metrics span {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--app-text-secondary);
  font-size: 12px;
}

.gateway-preset-grid {
  /* 预设卡片统一高度，避免不同厂商文案长度把按钮和标签挤乱。 */
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  grid-auto-rows: 1fr;
  align-items: stretch;
}

.gateway-preset-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.12), transparent 42%),
    rgba(255, 255, 255, 0.025);
}

.gateway-preset-card__header,
.gateway-preset-card__footer,
.gateway-preset-card__tags,
.gateway-preset-card__footer-actions {
  display: flex;
  gap: 10px;
}

.gateway-preset-card__header,
.gateway-preset-card__footer {
  align-items: flex-start;
  justify-content: space-between;
}

.gateway-preset-card__title-group,
.gateway-preset-card__body,
.gateway-preset-card__meta {
  display: grid;
  gap: 10px;
}

.gateway-preset-card__title-group {
  min-width: 0;
}

.gateway-preset-card__title-group strong {
  font-size: 16px;
  line-height: 1.45;
}

.gateway-preset-card__alias,
.gateway-preset-card__meta-label {
  color: var(--app-text-secondary);
  font-size: 12px;
  letter-spacing: 0.05em;
}

.gateway-preset-card__tags,
.gateway-preset-card__footer-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.gateway-preset-card__body {
  flex: 1;
  align-content: start;
}

.gateway-preset-card__summary,
.gateway-preset-card__body p,
.gateway-preset-card__note {
  margin: 0;
  line-height: 1.7;
}

.gateway-preset-card__summary,
.gateway-preset-card__note {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.gateway-preset-card__summary {
  min-height: calc(1.7em * 2);
  color: var(--app-text-secondary);
}

.gateway-preset-card__meta-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid rgba(149, 184, 223, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.035);
}

.gateway-preset-card__meta-value {
  overflow: hidden;
  color: var(--app-text);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.gateway-preset-card__note {
  min-height: calc(1.7em * 2);
  color: var(--app-text-secondary);
}

.gateway-preset-card__footer {
  margin-top: auto;
  padding-top: 4px;
}

.gateway-workspace {
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  align-items: start;
}

.gateway-list,
.gateway-detail {
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.02);
}

.gateway-list {
  align-content: start;
}

.gateway-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.gateway-list__overview,
.gateway-list__items {
  display: grid;
  gap: 12px;
}

.gateway-list__overview {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.gateway-list__metric {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid rgba(149, 184, 223, 0.08);
  border-radius: 16px;
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.1), transparent 40%),
    rgba(255, 255, 255, 0.028);
}

.gateway-list__metric-label,
.gateway-list__hint {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.gateway-list__metric strong {
  font-size: 20px;
  line-height: 1.2;
}

.gateway-list__hint {
  margin: 0;
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
  border-color: rgba(255, 138, 31, 0.36);
}

.gateway-summary--active {
  border-color: rgba(255, 138, 31, 0.5);
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.14), transparent 36%),
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

.gateway-detail__model-metrics {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.gateway-detail__model-metric {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(149, 184, 223, 0.08);
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.1), transparent 40%),
    rgba(255, 255, 255, 0.028);
}

.gateway-detail__model-metric-label {
  color: var(--app-text-secondary);
  font-size: 12px;
  letter-spacing: 0.05em;
}

.gateway-detail__model-metric strong {
  font-size: 22px;
  line-height: 1.2;
}

.gateway-detail__model-pagination {
  padding-top: 4px;
  border-top: 1px solid rgba(149, 184, 223, 0.12);
}

.settings-pagination {
  flex-wrap: wrap;
}

.mono-text {
  font-family: "JetBrains Mono", "Consolas", monospace;
}

@media (max-width: 1440px) {
  .account-overview,
  .company-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1280px) {
  .gateway-workspace,
  .filter-grid,
  .filter-grid--users,
  .account-overview,
  .company-overview,
  .password-request-grid,
  .gateway-detail__model-metrics {
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

  .gateway-preset-card__header,
  .gateway-preset-card__footer {
    flex-direction: column;
  }

  .gateway-preset-card__tags,
  .gateway-preset-card__footer-actions {
    justify-content: flex-start;
  }

  .gateway-list__overview {
    grid-template-columns: 1fr;
  }
}
</style>
