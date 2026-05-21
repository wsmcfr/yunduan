<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Lock,
  Message,
  OfficeBuilding,
  Promotion,
  User,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import {
  fetchAuthRuntimeOptionsRequest,
  forgotPasswordRequest,
  resetPasswordRequest,
} from "@/services/api/auth";
import { mapAuthRuntimeOptionsDto } from "@/services/mappers/commonMappers";
import { routeNames } from "@/router/routes";
import { useAuthStore } from "@/stores/auth";
import type { RegisterMode } from "@/types/api";
import type { AuthRuntimeOptions, RegisterResponse } from "@/types/models";

type PublicAuthPanel = "login" | "register" | "forgot";
type RegisterStep = "profile" | "security";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

/**
 * 认证页运行时能力。
 * 即使该接口暂时失败，也保留一份安全默认值，避免页面无法继续使用。
 */
const runtimeOptions = ref<AuthRuntimeOptions>({
  registrationEnabled: true,
  passwordResetEnabled: false,
  passwordPolicyHint: "密码需为 8-128 位，并至少包含大写字母、小写字母、数字、符号中的三类。",
});

// 公共认证入口在登录、注册、找回密码三块之间切换。
const activePanel = ref<PublicAuthPanel>("login");
// 注册表单字段较多，拆成两步显示，避免右侧认证卡片出现突兀的浏览器滚动条。
const activeRegisterStep = ref<RegisterStep>("profile");

// 不同流程的提交状态分别维护，避免一个流程锁死整页。
const loginLoading = ref(false);
const registerLoading = ref(false);
const forgotLoading = ref(false);
const resetLoading = ref(false);

// 邮件找回与管理员申请都需要保留成功提示，便于用户继续下一步。
const forgotSuccessNotice = ref("");
const registerSuccessNotice = ref("");

/**
 * 登录表单状态。
 * 正式认证页不预填任何账号或密码，避免敏感信息出现在公网页面。
 */
const loginFormState = reactive({
  account: "",
  password: "",
});

/**
 * 注册表单状态。
 * 这里同时承载“邀请码加入公司”和“申请新公司管理员”两条路径。
 */
const registerFormState = reactive({
  registerMode: "invite_join" as RegisterMode,
  username: "",
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
  inviteCode: "",
  companyName: "",
  companyContactName: "",
  companyNote: "",
});

/**
 * 忘记密码表单状态。
 * 找回流程统一按邮箱发起，避免公开接口暴露账号存在性。
 */
const forgotFormState = reactive({
  email: "",
});

/**
 * 重置密码表单状态。
 * token 既可能来自邮件链接，也可能由用户手动粘贴。
 */
const resetFormState = reactive({
  token: "",
  newPassword: "",
  confirmPassword: "",
});

// 当前是否处于“邮件链接跳转后的重置密码”视图。
const isResetRoute = computed(() => route.name === routeNames.resetPassword);

// 注册页当前是否走“邀请码加入公司”路径。
const isInviteJoinMode = computed(() => registerFormState.registerMode === "invite_join");

/**
 * 注册页步骤配置。
 * 第一步只收集身份与公司加入方式，第二步再处理密码与提交，保证单屏内信息密度稳定。
 */
const REGISTER_STEP_OPTIONS: Array<{
  name: RegisterStep;
  title: string;
  description: string;
}> = [
  {
    name: "profile",
    title: "身份资料",
    description: "账号、邮箱和公司加入方式",
  },
  {
    name: "security",
    title: "安全确认",
    description: "密码策略与最终提交",
  },
];

/**
 * 登录页左侧检测流程。
 * 这些步骤不参与业务计算，只用于填充首屏顶部空白并说明系统从现场到追溯的主链路。
 */
const LOGIN_PROCESS_STEPS = [
  {
    title: "现场采集",
    description: "设备端完成拍摄与检测结果上报。",
  },
  {
    title: "云端归档",
    description: "记录、图片和上下文统一入库。",
  },
  {
    title: "复核判定",
    description: "人工复核结合 AI 建议确认风险。",
  },
  {
    title: "统计追溯",
    description: "按公司、设备、零件和日期复盘。",
  },
];

/**
 * 登录页左侧平台覆盖范围。
 * 使用静态短标签展示登录后的主要工作面，避免底部只剩大块装饰留白。
 */
const LOGIN_COVERAGE_ITEMS = [
  "检测记录",
  "样本图库",
  "设备管理",
  "零件台账",
  "统计分析",
  "系统设置",
];

/**
 * 登录页左侧运行快照。
 * 这些是入口页的静态示意指标，目的是解释进入系统后会优先看到哪些运行信息。
 */
const LOGIN_SNAPSHOT_ITEMS = [
  {
    label: "今日检测",
    value: "实时",
    description: "设备上传后自动进入记录池。",
  },
  {
    label: "风险记录",
    value: "优先",
    description: "不良和待确认记录置顶处理。",
  },
  {
    label: "待审核",
    value: "闭环",
    description: "人工复核与 AI 建议并行辅助。",
  },
  {
    label: "样本覆盖",
    value: "归档",
    description: "良品与缺陷图片沉淀到图库。",
  },
];

/**
 * 登录页左侧能力卡。
 * 每张卡用短说明加具体工作项填充，保证桌面高屏或矮屏拉伸时卡片内部仍有可扫读内容。
 */
const LOGIN_HIGHLIGHT_ITEMS = [
  {
    title: "统一检测入口",
    description: "集中查看设备上传的检测记录、样本图片和零件基础信息。",
    actions: ["记录筛选", "样本留档", "零件关联"],
  },
  {
    title: "审核闭环",
    description: "风险记录进入人工复核与 AI 辅助研判，减少漏判和重复追查。",
    actions: ["人工复核", "AI 建议", "结果改判"],
  },
  {
    title: "数据留痕",
    description: "按公司、设备、零件和时间沉淀统计数据，为追溯和复盘提供依据。",
    actions: ["公司维度", "设备维度", "趋势复盘"],
  },
];

/**
 * 认证卡底部工作区预览。
 * 这里不做跳转，避免未登录状态下出现无效入口，只作为登录后可见能力的说明。
 */
const LOGIN_WORKSPACE_PREVIEW_ITEMS = [
  {
    title: "仪表盘",
    description: "先看检测规模、风险热点和审核闭环。",
  },
  {
    title: "检测记录",
    description: "进入单条记录查看图片、上下文和复核结果。",
  },
  {
    title: "样本图库",
    description: "按零件类型沉淀良品与缺陷样本。",
  },
  {
    title: "统计分析",
    description: "追踪趋势、缺陷结构和设备风险排行。",
  },
];

/**
 * 认证卡内的账号路径说明。
 * 它填补表单与工作区预览之间的空白，同时解释当前三个认证标签页各自适合的场景。
 */
const LOGIN_AUTH_PATH_ITEMS = [
  {
    title: "公司成员入口",
    description: "使用用户名或邮箱进入已授权公司的检测控制台。",
  },
  {
    title: "新成员加入",
    description: "通过管理员发放的邀请码绑定公司与账号角色。",
  },
  {
    title: "账号恢复",
    description: "邮件通道开启后使用一次性令牌重置密码。",
  },
];

/**
 * 登录表单下方的上下文信息。
 * 这些内容用于填充宽屏表单区，说明登录后的默认落点和主要处理对象。
 */
const LOGIN_SIGNIN_CONTEXT_ITEMS = [
  {
    label: "默认入口",
    value: "运营态势总览",
    description: "先查看检测规模、风险热点和审核闭环。",
  },
  {
    label: "优先处理",
    value: "待复核记录",
    description: "从风险记录进入图片证据和人工复核。",
  },
];

/**
 * 当前注册步骤索引。
 * 翻页按钮复用这里的索引，避免多个按钮各自判断边界。
 */
const activeRegisterStepIndex = computed(() =>
  Math.max(
    REGISTER_STEP_OPTIONS.findIndex((item) => item.name === activeRegisterStep.value),
    0,
  ),
);

/**
 * 根据注册模式返回按钮文案，让用户一眼知道当前提交会发生什么。
 */
const registerSubmitText = computed(() =>
  isInviteJoinMode.value ? "创建账号并加入公司" : "提交新公司管理员申请",
);

/**
 * 根据注册模式返回表单说明。
 * 普通成员走邀请码直接入司；新公司管理员需要进入审批队列。
 */
const registerModeSummary = computed(() =>
  isInviteJoinMode.value
    ? "适合普通成员或复核员。输入公司管理员提供的邀请码后，注册成功会直接加入对应公司并自动登录。"
    : "适合要新开独立公司的负责人。提交后不会立即登录，需要等待平台默认管理员审批通过。",
);

/**
 * 读取认证运行时能力。
 * 这里失败时不打断主流程，继续使用默认值。
 */
async function loadRuntimeOptions(): Promise<void> {
  try {
    const response = await fetchAuthRuntimeOptionsRequest();
    runtimeOptions.value = mapAuthRuntimeOptionsDto(response);
  } catch {
    // 运行时能力只是辅助信息；接口失败时不影响用户继续尝试主流程。
  }
}

/**
 * 解析登录成功后的目标跳转地址。
 * 如果没有 redirect 参数，就回到系统默认首页。
 */
function resolveRedirectTarget(): string {
  return typeof route.query.redirect === "string" && route.query.redirect.length > 0
    ? route.query.redirect
    : "/dashboard";
}

/**
 * 清理登录表单里的敏感密码字段，减少密码在前端内存中的停留时间。
 */
function clearLoginSensitiveFields(): void {
  loginFormState.password = "";
}

/**
 * 清理注册表单里的敏感密码字段。
 */
function clearRegisterSensitiveFields(): void {
  registerFormState.password = "";
  registerFormState.confirmPassword = "";
}

/**
 * 清理注册表单里的业务字段。
 * 提交成功后统一重置，避免上一轮申请资料残留到下一次注册。
 */
function clearRegisterBusinessFields(): void {
  registerFormState.username = "";
  registerFormState.displayName = "";
  registerFormState.email = "";
  registerFormState.inviteCode = "";
  registerFormState.companyName = "";
  registerFormState.companyContactName = "";
  registerFormState.companyNote = "";
}

/**
 * 把注册表单恢复到默认状态。
 */
function resetRegisterForm(): void {
  registerFormState.registerMode = "invite_join";
  activeRegisterStep.value = "profile";
  clearRegisterSensitiveFields();
  clearRegisterBusinessFields();
}

/**
 * 清理重置密码表单中的敏感字段。
 * 某些失败重试场景需要保留 token，因此这里允许按需保留。
 */
function clearResetSensitiveFields(preserveToken = true): void {
  if (!preserveToken) {
    resetFormState.token = "";
  }
  resetFormState.newPassword = "";
  resetFormState.confirmPassword = "";
}

/**
 * 校验注册表单的公共字段。
 * 公共字段不完整时直接阻止提交，避免发送无意义请求。
 */
function validateCommonRegisterFields(): boolean {
  if (
    !registerFormState.username.trim()
    || !registerFormState.displayName.trim()
    || !registerFormState.email.trim()
    || !registerFormState.password
  ) {
    ElMessage.warning("请完整填写用户名、显示名称、邮箱和密码。");
    return false;
  }

  if (registerFormState.password !== registerFormState.confirmPassword) {
    ElMessage.warning("两次输入的密码不一致。");
    return false;
  }

  return true;
}

/**
 * 校验当前注册模式下的专属字段。
 * 邀请码路径和管理员申请路径需要的资料完全不同，不能混用。
 */
function validateModeSpecificRegisterFields(): boolean {
  if (isInviteJoinMode.value) {
    if (!registerFormState.inviteCode.trim()) {
      ElMessage.warning("请输入公司邀请码。");
      return false;
    }
    return true;
  }

  if (!registerFormState.companyName.trim()) {
    ElMessage.warning("请输入申请开通的公司名称。");
    return false;
  }
  if (!registerFormState.companyContactName.trim()) {
    ElMessage.warning("请输入公司联系人。");
    return false;
  }

  return true;
}

/**
 * 注册步骤翻页。
 * 表单本身不再依赖纵向滚动，字段太多时交给步骤切换承接。
 */
function stepRegisterPage(direction: -1 | 1): void {
  const nextIndex = Math.min(
    Math.max(activeRegisterStepIndex.value + direction, 0),
    REGISTER_STEP_OPTIONS.length - 1,
  );
  activeRegisterStep.value = REGISTER_STEP_OPTIONS[nextIndex]?.name ?? "profile";
}

/**
 * 处理登录。
 */
async function handleLogin(): Promise<void> {
  if (!loginFormState.account.trim()) {
    ElMessage.warning("请输入用户名或邮箱。");
    return;
  }
  if (!loginFormState.password) {
    ElMessage.warning("请输入密码。");
    return;
  }

  loginLoading.value = true;
  try {
    await authStore.login(loginFormState.account, loginFormState.password);
    registerSuccessNotice.value = "";
    clearLoginSensitiveFields();
    ElMessage.success("登录成功。");
    await router.push(resolveRedirectTarget());
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "登录失败。");
  } finally {
    loginLoading.value = false;
  }
}

/**
 * 根据当前注册模式组装注册请求。
 * 这样可以把分支逻辑集中在一个地方，避免模板和提交函数到处散落判断。
 */
async function submitRegisterRequest(): Promise<RegisterResponse> {
  if (isInviteJoinMode.value) {
    return authStore.register({
      registerMode: "invite_join",
      username: registerFormState.username.trim(),
      displayName: registerFormState.displayName.trim(),
      email: registerFormState.email.trim(),
      password: registerFormState.password,
      inviteCode: registerFormState.inviteCode.trim(),
    });
  }

  return authStore.register({
    registerMode: "company_admin_request",
    username: registerFormState.username.trim(),
    displayName: registerFormState.displayName.trim(),
    email: registerFormState.email.trim(),
    password: registerFormState.password,
    companyName: registerFormState.companyName.trim(),
    companyContactName: registerFormState.companyContactName.trim(),
    companyNote: registerFormState.companyNote.trim() || null,
  });
}

/**
 * 处理注册。
 * 邀请码入司成功后直接跳转；新公司管理员申请则提示等待审批。
 */
async function handleRegister(): Promise<void> {
  if (!runtimeOptions.value.registrationEnabled) {
    ElMessage.warning("当前环境未开放自助注册。");
    return;
  }

  registerSuccessNotice.value = "";

  if (!validateCommonRegisterFields() || !validateModeSpecificRegisterFields()) {
    return;
  }

  registerLoading.value = true;
  try {
    const result = await submitRegisterRequest();
    clearRegisterSensitiveFields();

    if (result.status === "authenticated") {
      clearRegisterBusinessFields();
      ElMessage.success(result.message);
      await router.push(resolveRedirectTarget());
      return;
    }

    registerSuccessNotice.value = `${result.message} 审批通过后，再回到登录页使用你注册的账号登录即可。`;
    resetRegisterForm();
    activePanel.value = "login";
    ElMessage.success(result.message);
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "注册失败。");
  } finally {
    registerLoading.value = false;
  }
}

/**
 * 处理忘记密码。
 */
async function handleForgotPassword(): Promise<void> {
  if (!runtimeOptions.value.passwordResetEnabled) {
    ElMessage.warning("当前环境尚未开启邮件找回，请联系管理员。");
    return;
  }
  if (!forgotFormState.email.trim()) {
    ElMessage.warning("请输入注册邮箱。");
    return;
  }

  forgotLoading.value = true;
  try {
    const response = await forgotPasswordRequest({
      email: forgotFormState.email.trim(),
    });
    forgotSuccessNotice.value = `${response.message} 请检查收件箱和垃圾箱；如果链接无法直接打开，可复制邮件中的一次性令牌，在重置页面手动提交。`;
    forgotFormState.email = "";
    ElMessage.success(response.message);
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "密码找回申请失败。");
  } finally {
    forgotLoading.value = false;
  }
}

/**
 * 处理重置密码。
 */
async function handleResetPassword(): Promise<void> {
  if (!resetFormState.token.trim() || !resetFormState.newPassword) {
    ElMessage.warning("请填写完整的重置令牌和新密码。");
    return;
  }
  if (resetFormState.newPassword !== resetFormState.confirmPassword) {
    ElMessage.warning("两次输入的新密码不一致。");
    return;
  }

  resetLoading.value = true;
  try {
    const response = await resetPasswordRequest({
      token: resetFormState.token.trim(),
      new_password: resetFormState.newPassword,
    });
    clearResetSensitiveFields(false);
    ElMessage.success(response.message);
    activePanel.value = "login";
    await router.replace({
      name: routeNames.login,
      query: typeof route.query.redirect === "string" ? { redirect: route.query.redirect } : {},
    });
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "密码重置失败。");
  } finally {
    resetLoading.value = false;
  }
}

/**
 * 回到登录视图。
 * 重置密码完成后，统一落回普通登录页。
 */
async function backToLogin(): Promise<void> {
  activePanel.value = "login";
  clearResetSensitiveFields(false);
  await router.replace({
    name: routeNames.login,
    query: typeof route.query.redirect === "string" ? { redirect: route.query.redirect } : {},
  });
}

/**
 * 从找回密码面板直接进入重置密码页。
 * 邮件客户端不支持自动打开链接时，用户也能手动粘贴令牌继续完成流程。
 */
async function openResetPasswordPage(): Promise<void> {
  await router.push({
    name: routeNames.resetPassword,
    query: typeof route.query.redirect === "string" ? { redirect: route.query.redirect } : {},
  });
}

/**
 * 把 URL 里的重置 token 同步到表单，支持从邮件链接直接落地到输入框。
 */
watch(
  () => route.query.token,
  (tokenValue) => {
    resetFormState.token = typeof tokenValue === "string" ? tokenValue.trim() : "";
  },
  { immediate: true },
);

/**
 * 当路由回到普通登录页时，确保公共标签页处于可用状态。
 */
watch(
  () => isResetRoute.value,
  (nextValue) => {
    if (!nextValue && !["login", "register", "forgot"].includes(activePanel.value)) {
      activePanel.value = "login";
    }
  },
  { immediate: true },
);

onMounted(() => {
  void loadRuntimeOptions();
});
</script>

<template>
  <div class="login-page">
    <section class="login-page__hero">
      <div class="login-page__process-strip" aria-label="检测处理流程">
        <div
          v-for="(item, index) in LOGIN_PROCESS_STEPS"
          :key="item.title"
          class="login-page__process-item"
        >
          <span>0{{ index + 1 }}</span>
          <strong>{{ item.title }}</strong>
          <small>{{ item.description }}</small>
        </div>
      </div>

      <div class="login-page__hero-main">
        <div class="login-page__hero-copy">
          <div class="login-page__system-card">
            <span class="login-page__system-kicker">Cloud Console</span>
            <strong>工业缺陷检测云端控制台</strong>
            <p>从采集上传到复核归档，所有关键检测数据在同一个入口处理。</p>
          </div>

          <span class="login-page__eyebrow">Industrial Defect Detection</span>
          <h1 class="login-page__title">云端检测系统</h1>
          <p class="login-page__description">
            面向工业缺陷检测现场的云端控制台，统一管理检测记录、样本图库、设备状态、零件台账与统计分析。
            系统支持人工复核与 AI 辅助研判，帮助管理员快速定位风险记录、追踪处理闭环并沉淀可追溯数据。
          </p>
        </div>

        <section class="login-page__support-grid" aria-label="系统入口信息">
          <div class="login-page__snapshot" aria-label="运行快照">
            <div class="login-page__snapshot-header">
              <span>Runtime Snapshot</span>
              <strong>运行快照</strong>
            </div>

            <div class="login-page__snapshot-grid">
              <article
                v-for="item in LOGIN_SNAPSHOT_ITEMS"
                :key="item.label"
                class="login-page__snapshot-item"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.description }}</small>
              </article>
            </div>
          </div>

          <div class="login-page__coverage" aria-label="平台覆盖范围">
            <div class="login-page__coverage-header">
              <span>Platform Scope</span>
              <strong>平台覆盖范围</strong>
            </div>
            <div class="login-page__coverage-grid">
              <span
                v-for="item in LOGIN_COVERAGE_ITEMS"
                :key="item"
              >
                {{ item }}
              </span>
            </div>
          </div>
        </section>

        <div class="login-page__highlights">
          <article
            v-for="item in LOGIN_HIGHLIGHT_ITEMS"
            :key="item.title"
            class="login-page__highlight app-panel"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.description }}</span>
            <ul class="login-page__highlight-list">
              <li
                v-for="action in item.actions"
                :key="action"
              >
                {{ action }}
              </li>
            </ul>
          </article>
        </div>
      </div>
    </section>

    <section class="login-page__form-card app-panel">
      <PageHeader
        eyebrow="Access"
        :title="isResetRoute ? '重置密码' : '认证中心'"
        :description="
          isResetRoute
            ? '输入邮件中的重置令牌和新密码，完成一次性密码更新。'
            : '登录、注册、公司加入与密码找回都统一在这里处理。'
        "
      />

      <template v-if="isResetRoute">
        <ElAlert
          class="login-page__alert"
          title="安全提醒"
          type="info"
          :closable="false"
          description="重置成功后，旧密码立即失效，旧登录会话也会被系统判定为失效。"
        />

        <ElForm class="login-page__form" label-position="top" @submit.prevent="handleResetPassword">
          <ElFormItem label="重置令牌">
            <ElInput
              v-model="resetFormState.token"
              :prefix-icon="Lock"
              placeholder="请输入邮件中的重置令牌"
            />
          </ElFormItem>

          <ElFormItem label="新密码">
            <ElInput
              v-model="resetFormState.newPassword"
              :prefix-icon="Lock"
              show-password
              type="password"
              placeholder="请输入新密码"
            />
          </ElFormItem>

          <ElFormItem label="确认新密码">
            <ElInput
              v-model="resetFormState.confirmPassword"
              :prefix-icon="Lock"
              show-password
              type="password"
              placeholder="请再次输入新密码"
            />
          </ElFormItem>

          <p class="login-page__policy">{{ runtimeOptions.passwordPolicyHint }}</p>

          <div class="login-page__actions">
            <ElButton class="login-page__secondary" plain size="large" @click="backToLogin">
              返回登录
            </ElButton>
            <ElButton
              class="login-page__submit"
              color="var(--app-primary)"
              native-type="submit"
              :loading="resetLoading"
              size="large"
            >
              提交重置
            </ElButton>
          </div>
        </ElForm>
      </template>

      <ElTabs v-else v-model="activePanel" class="login-page__tabs" stretch>
        <ElTabPane label="登录" name="login">
          <ElAlert
            v-if="registerSuccessNotice"
            class="login-page__alert"
            title="申请已提交"
            type="success"
            :closable="false"
            :description="registerSuccessNotice"
          />

          <ElForm
            class="login-page__form login-page__login-grid"
            label-position="top"
            @submit.prevent="handleLogin"
          >
            <ElFormItem label="账号">
              <ElInput
                v-model="loginFormState.account"
                :prefix-icon="User"
                placeholder="请输入用户名或邮箱"
              />
            </ElFormItem>

            <ElFormItem label="密码">
              <ElInput
                v-model="loginFormState.password"
                :prefix-icon="Lock"
                placeholder="请输入密码"
                show-password
                type="password"
              />
            </ElFormItem>

            <ElButton
              class="login-page__submit login-page__login-submit"
              color="var(--app-primary)"
              native-type="submit"
              :loading="loginLoading"
              size="large"
            >
              进入系统
            </ElButton>

            <div class="login-page__signin-context" aria-label="登录后处理重点">
              <article
                v-for="item in LOGIN_SIGNIN_CONTEXT_ITEMS"
                :key="item.label"
                class="login-page__signin-context-item"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.description }}</small>
              </article>
            </div>
          </ElForm>
        </ElTabPane>

        <ElTabPane label="注册" name="register">
          <ElAlert
            v-if="!runtimeOptions.registrationEnabled"
            class="login-page__alert"
            title="当前环境未开放自助注册"
            type="warning"
            :closable="false"
            description="如果需要新账号，请联系管理员开通，或后续在服务器配置中开启公开注册。"
          />

          <ElForm
            v-else
            class="login-page__form"
            label-position="top"
            @submit.prevent="handleRegister"
          >
            <div class="login-page__stepper" aria-label="注册步骤">
              <button
                v-for="(item, index) in REGISTER_STEP_OPTIONS"
                :key="item.name"
                type="button"
                class="login-page__stepper-item"
                :class="{ 'login-page__stepper-item--active': activeRegisterStep === item.name }"
                @click="activeRegisterStep = item.name"
              >
                <span>0{{ index + 1 }}</span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.description }}</small>
              </button>
            </div>

            <section
              v-show="activeRegisterStep === 'profile'"
              class="login-page__step-page login-page__step-page--active"
            >
              <div class="login-page__mode-switch">
                <ElRadioGroup v-model="registerFormState.registerMode" size="large">
                  <ElRadioButton value="invite_join">
                    <strong>邀请码加入公司</strong>
                    <small>已有公司成员，拿到邀请码后直接绑定公司。</small>
                  </ElRadioButton>
                  <ElRadioButton value="company_admin_request">
                    <strong>申请新公司管理员</strong>
                    <small>新公司负责人，提交资料后等待平台审批。</small>
                  </ElRadioButton>
                </ElRadioGroup>
                <p class="login-page__mode-note">{{ registerModeSummary }}</p>
              </div>

              <div class="login-page__field-grid">
                <ElFormItem label="用户名">
                  <ElInput
                    v-model="registerFormState.username"
                    :prefix-icon="User"
                    placeholder="请输入用户名"
                  />
                </ElFormItem>

                <ElFormItem label="显示名称">
                  <ElInput
                    v-model="registerFormState.displayName"
                    :prefix-icon="User"
                    placeholder="请输入显示名称"
                  />
                </ElFormItem>

                <ElFormItem label="邮箱" class="login-page__field-grid-wide">
                  <ElInput
                    v-model="registerFormState.email"
                    :prefix-icon="Message"
                    placeholder="请输入可接收邮件的邮箱"
                  />
                </ElFormItem>

                <ElFormItem
                  v-if="isInviteJoinMode"
                  label="公司邀请码"
                  class="login-page__field-grid-wide"
                >
                  <ElInput
                    v-model="registerFormState.inviteCode"
                    :prefix-icon="Promotion"
                    placeholder="请输入公司管理员提供的邀请码"
                  />
                </ElFormItem>

                <template v-else>
                  <ElFormItem label="公司名称">
                    <ElInput
                      v-model="registerFormState.companyName"
                      :prefix-icon="OfficeBuilding"
                      placeholder="请输入准备创建的公司名称"
                    />
                  </ElFormItem>

                  <ElFormItem label="联系人">
                    <ElInput
                      v-model="registerFormState.companyContactName"
                      :prefix-icon="User"
                      placeholder="请输入公司联系人"
                    />
                  </ElFormItem>
                </template>
              </div>
            </section>

            <section
              v-show="activeRegisterStep === 'security'"
              class="login-page__step-page login-page__step-page--active"
            >
              <ElFormItem
                v-if="!isInviteJoinMode"
                label="申请备注"
              >
                <ElInput
                  v-model="registerFormState.companyNote"
                  class="login-page__textarea"
                  type="textarea"
                  :rows="3"
                  resize="vertical"
                  placeholder="可填写业务场景、设备规模或其他审批说明"
                />
              </ElFormItem>

              <div class="login-page__field-grid">
                <ElFormItem label="密码">
                  <ElInput
                    v-model="registerFormState.password"
                    :prefix-icon="Lock"
                    placeholder="请输入密码"
                    show-password
                    type="password"
                  />
                </ElFormItem>

                <ElFormItem label="确认密码">
                  <ElInput
                    v-model="registerFormState.confirmPassword"
                    :prefix-icon="Lock"
                    placeholder="请再次输入密码"
                    show-password
                    type="password"
                  />
                </ElFormItem>
              </div>

              <p class="login-page__policy">{{ runtimeOptions.passwordPolicyHint }}</p>
            </section>

            <div class="login-page__step-actions">
              <ElButton
                plain
                native-type="button"
                size="large"
                :disabled="activeRegisterStepIndex <= 0"
                @click="stepRegisterPage(-1)"
              >
                上一步
              </ElButton>
              <ElButton
                v-if="activeRegisterStep !== 'security'"
                type="primary"
                plain
                native-type="button"
                size="large"
                @click="stepRegisterPage(1)"
              >
                下一步
              </ElButton>
              <ElButton
                v-else
                class="login-page__submit"
                color="var(--app-primary)"
                native-type="submit"
                :loading="registerLoading"
                size="large"
              >
                {{ registerSubmitText }}
              </ElButton>
            </div>
          </ElForm>
        </ElTabPane>

        <ElTabPane label="找回密码" name="forgot">
          <ElAlert
            v-if="!runtimeOptions.passwordResetEnabled"
            class="login-page__alert"
            title="当前环境未开启邮件找回"
            type="warning"
            :closable="false"
            description="后端邮件通道配置完成后，这里会向你的邮箱发送一次性重置链接。"
          />

          <template v-else>
            <ElAlert
              v-if="forgotSuccessNotice"
              class="login-page__alert"
              title="重置邮件已发出"
              type="success"
              :closable="false"
              :description="forgotSuccessNotice"
            />

            <ElForm
              class="login-page__form"
              label-position="top"
              @submit.prevent="handleForgotPassword"
            >
              <ElFormItem label="邮箱">
                <ElInput
                  v-model="forgotFormState.email"
                  :prefix-icon="Message"
                  placeholder="请输入注册邮箱"
                />
              </ElFormItem>

              <p class="login-page__policy">
                系统不会公开告知该邮箱是否已注册；如果账号存在，会向邮箱发送一次性重置链接。
              </p>

              <ElButton
                class="login-page__submit"
                color="var(--app-primary)"
                native-type="submit"
                :loading="forgotLoading"
                size="large"
              >
                发送重置邮件
              </ElButton>
            </ElForm>

            <div v-if="forgotSuccessNotice" class="login-page__actions login-page__actions--single">
              <ElButton
                class="login-page__submit"
                color="var(--app-primary)"
                size="large"
                @click="openResetPasswordPage"
              >
                前往重置页面
              </ElButton>
            </div>
          </template>
        </ElTabPane>
      </ElTabs>

      <section class="login-page__auth-paths" aria-label="账号路径说明">
        <div class="login-page__auth-paths-header">
          <span>Account Paths</span>
          <strong>账号路径说明</strong>
        </div>

        <div class="login-page__auth-paths-grid">
          <article
            v-for="item in LOGIN_AUTH_PATH_ITEMS"
            :key="item.title"
            class="login-page__auth-path"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.description }}</span>
          </article>
        </div>
      </section>

      <section class="login-page__workspace-preview" aria-label="登录后工作区预览">
        <div class="login-page__workspace-preview-header">
          <span>Workspace Preview</span>
          <strong>登录后工作区预览</strong>
        </div>

        <div class="login-page__workspace-grid">
          <article
            v-for="item in LOGIN_WORKSPACE_PREVIEW_ITEMS"
            :key="item.title"
            class="login-page__workspace-item"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.description }}</span>
          </article>
        </div>
      </section>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 28px;
  height: 100dvh;
  min-height: 100dvh;
  padding: 28px;
  width: 100%;
  position: relative;
  align-items: stretch;
  overflow-x: hidden;
  overflow-y: hidden;
}

.login-page::before,
.login-page::after {
  content: "";
  position: absolute;
  inset: auto;
  pointer-events: none;
  border-radius: 999px;
  filter: blur(10px);
}

.login-page::before {
  top: 36px;
  right: 18%;
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, rgba(74, 212, 154, 0.14), transparent 72%);
}

.login-page::after {
  left: 4%;
  bottom: 8%;
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, rgba(93, 151, 242, 0.16), transparent 74%);
}

.login-page__hero {
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  align-content: stretch;
  gap: clamp(12px, 1.65vh, 18px);
  height: calc(100dvh - 56px);
  min-height: calc(100dvh - 56px);
  padding: clamp(34px, 4vw, 52px);
  border: 1px solid rgba(149, 184, 223, 0.14);
  border-radius: 34px;
  background:
    radial-gradient(circle at top right, rgba(74, 212, 154, 0.12), transparent 34%),
    radial-gradient(circle at bottom left, rgba(93, 151, 242, 0.14), transparent 36%),
    linear-gradient(145deg, rgba(11, 25, 43, 0.92), rgba(10, 22, 38, 0.82));
  overflow: hidden;
}

.login-page__process-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  position: relative;
  z-index: 1;
}

.login-page__process-item {
  display: grid;
  gap: 5px;
  min-height: 104px;
  padding: 14px 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.012)),
    rgba(8, 19, 33, 0.28);
}

.login-page__process-item span {
  color: var(--app-copper);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.login-page__process-item strong {
  color: var(--app-text);
  font-size: 15px;
  line-height: 1.35;
}

.login-page__process-item small {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.login-page__hero::after {
  content: "";
  position: absolute;
  pointer-events: none;
}

.login-page__hero::after {
  left: -72px;
  bottom: -92px;
  width: 260px;
  height: 260px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(255, 138, 31, 0.1), transparent 70%);
}

.login-page__system-card {
  display: grid;
  gap: 12px;
  width: min(100%, 620px);
  padding: 18px 22px;
  position: relative;
  z-index: 1;
  border: 1px solid rgba(149, 184, 223, 0.1);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(10px);
}

.login-page__hero-main {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
  grid-template-rows: max-content minmax(max-content, 1fr);
  gap: 18px;
  position: relative;
  z-index: 1;
  min-height: 0;
}

.login-page__hero-copy {
  display: grid;
  align-content: start;
  gap: 18px;
  min-width: 0;
}

.login-page__system-card strong {
  margin: 0;
  color: #e4eef8;
  font-size: clamp(22px, 2.6vw, 32px);
  font-weight: 700;
  line-height: 1.2;
}

.login-page__system-card p {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.login-page__system-kicker {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.login-page__eyebrow {
  color: var(--app-primary);
  letter-spacing: 0.18em;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  position: relative;
  z-index: 1;
}

.login-page__title {
  margin: 0;
  max-width: 620px;
  font-size: clamp(32px, 3.2vw, 48px);
  line-height: 1.08;
  text-wrap: balance;
  position: relative;
  z-index: 1;
}

.login-page__description {
  max-width: 660px;
  color: var(--app-text-secondary);
  font-size: 16px;
  line-height: 1.95;
  position: relative;
  z-index: 1;
}

.login-page__highlights {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  min-height: 0;
  position: relative;
  z-index: 1;
}

.login-page__highlight {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 15px 16px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.015)),
    rgba(8, 19, 33, 0.3);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.login-page__highlight:first-child {
  grid-column: auto;
}

.login-page__highlight span {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.login-page__highlight-list {
  display: grid;
  gap: 7px;
  margin: auto 0 0;
  padding: 0;
  list-style: none;
}

.login-page__highlight-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text);
  font-size: 12px;
  font-weight: 700;
}

.login-page__highlight-list li::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--app-primary);
  box-shadow: 0 0 12px rgba(74, 212, 154, 0.36);
}

.login-page__coverage {
  display: grid;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.01)),
    rgba(8, 19, 33, 0.24);
}

.login-page__snapshot {
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.028), rgba(255, 255, 255, 0.01)),
    rgba(8, 19, 33, 0.24);
}

.login-page__support-grid {
  display: grid;
  gap: 12px;
  position: relative;
  z-index: 1;
  align-content: start;
  min-width: 0;
}

.login-page__coverage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.login-page__coverage-header span,
.login-page__snapshot-header span,
.login-page__auth-paths-header span,
.login-page__workspace-preview-header span {
  color: var(--app-primary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.login-page__coverage-header strong,
.login-page__snapshot-header strong,
.login-page__auth-paths-header strong,
.login-page__workspace-preview-header strong {
  color: var(--app-text);
  font-size: 15px;
}

.login-page__snapshot-header,
.login-page__coverage-grid {
  display: grid;
}

.login-page__snapshot-header,
.login-page__auth-paths-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.login-page__snapshot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.login-page__snapshot-item {
  display: grid;
  gap: 5px;
  min-height: 66px;
  padding: 10px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.025);
}

.login-page__snapshot-item span {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.login-page__snapshot-item strong {
  color: var(--app-text);
  font-size: 16px;
  line-height: 1.2;
}

.login-page__snapshot-item small {
  color: var(--app-text-secondary);
  font-size: 11px;
  line-height: 1.45;
}

.login-page__coverage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.login-page__coverage-grid span {
  display: inline-grid;
  min-height: 34px;
  place-items: center;
  padding: 0 10px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 12px;
  color: var(--app-text-secondary);
  background: rgba(255, 255, 255, 0.025);
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.login-page__form-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  align-self: stretch;
  justify-self: stretch;
  height: calc(100dvh - 56px);
  min-height: calc(100dvh - 56px);
  max-height: calc(100dvh - 56px);
  padding: 34px 32px;
  border-radius: 30px;
  border: 1px solid rgba(149, 184, 223, 0.14);
  background:
    radial-gradient(circle at top center, rgba(255, 138, 31, 0.1), transparent 30%),
    linear-gradient(180deg, rgba(13, 28, 48, 0.94), rgba(10, 22, 38, 0.92));
  overflow-x: hidden;
  overflow-y: auto;
}

.login-page__form-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  background: linear-gradient(90deg, rgba(255, 138, 31, 0.96), rgba(63, 167, 255, 0.92));
}

.login-page__tabs {
  flex: 0 0 auto;
  min-height: 0;
  margin-top: 0;
}

.login-page__tabs :deep(.el-tabs__content) {
  display: block;
  overflow: visible;
}

.login-page__tabs :deep(.el-tab-pane) {
  min-width: 0;
}

.login-page__form {
  margin-top: 14px;
}

.login-page__login-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  align-items: end;
  padding: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.02);
}

.login-page__login-grid :deep(.el-form-item) {
  margin-bottom: 0;
}

.login-page__login-submit {
  grid-column: 1 / -1;
}

.login-page__signin-context {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 2px;
}

.login-page__signin-context-item {
  display: grid;
  gap: 5px;
  min-height: 78px;
  padding: 12px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.025);
}

.login-page__signin-context-item span {
  color: var(--app-copper);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.login-page__signin-context-item strong {
  color: var(--app-text);
  font-size: 14px;
}

.login-page__signin-context-item small {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.login-page__workspace-preview {
  display: grid;
  flex: 1 0 auto;
  gap: 14px;
  min-height: 0;
  align-self: stretch;
  padding: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.028), rgba(255, 255, 255, 0.01)),
    rgba(8, 19, 33, 0.28);
}

.login-page__auth-paths {
  display: grid;
  flex: 0 0 auto;
  gap: 12px;
  padding: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.026), rgba(255, 255, 255, 0.01)),
    rgba(8, 19, 33, 0.24);
}

.login-page__auth-paths-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.login-page__auth-path {
  display: grid;
  gap: 6px;
  min-height: 80px;
  padding: 12px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.024);
}

.login-page__auth-path strong {
  color: var(--app-text);
  font-size: 13px;
}

.login-page__auth-path span {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.login-page__workspace-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.login-page__workspace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.login-page__workspace-item {
  display: grid;
  gap: 6px;
  min-height: 84px;
  padding: 14px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.025);
}

.login-page__workspace-item strong {
  color: var(--app-text);
  font-size: 14px;
}

.login-page__workspace-item span {
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.login-page__alert {
  margin-top: 18px;
}

.login-page__alert--inline {
  margin-top: 0;
  margin-bottom: 18px;
}

.login-page__mode-switch {
  display: grid;
  gap: 10px;
  margin-bottom: 0;
  padding: 16px 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
}

.login-page__mode-switch :deep(.el-radio-group) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
}

.login-page__mode-switch :deep(.el-radio-button) {
  width: 100%;
}

.login-page__mode-switch :deep(.el-radio-button__inner) {
  display: grid;
  align-content: start;
  gap: 7px;
  width: 100%;
  min-height: 92px;
  padding: 14px;
  text-align: left;
  white-space: normal;
  line-height: 1.45;
}

.login-page__mode-switch :deep(.el-radio-button__inner strong),
.login-page__mode-switch :deep(.el-radio-button__inner small) {
  display: block;
}

.login-page__mode-switch :deep(.el-radio-button__inner strong) {
  color: var(--app-text);
  font-size: 14px;
}

.login-page__mode-switch :deep(.el-radio-button__inner small) {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.login-page__mode-switch :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner strong),
.login-page__mode-switch :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner small) {
  color: #1b1208;
}

.login-page__mode-note {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.login-page__policy {
  margin: 2px 0 16px;
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.login-page__stepper {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.login-page__stepper-item {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(149, 184, 223, 0.14);
  border-radius: 14px;
  color: var(--app-text-secondary);
  text-align: left;
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}

.login-page__stepper-item span {
  color: var(--app-copper);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.login-page__stepper-item strong {
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.35;
}

.login-page__stepper-item small {
  font-size: 12px;
  line-height: 1.45;
}

.login-page__stepper-item--active {
  border-color: rgba(255, 138, 31, 0.5);
  background:
    radial-gradient(circle at top right, rgba(255, 138, 31, 0.14), transparent 38%),
    rgba(255, 255, 255, 0.04);
}

.login-page__step-page {
  display: grid;
  gap: 14px;
  align-content: start;
}

.login-page__field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.login-page__field-grid-wide {
  grid-column: 1 / -1;
}

.login-page__step-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.login-page__step-actions :deep(.el-button) {
  width: 100%;
  margin: 0;
}

.login-page__actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 12px;
}

.login-page__actions--single {
  grid-template-columns: 1fr;
  margin-top: 18px;
}

.login-page__secondary,
.login-page__submit {
  width: 100%;
  margin-top: 10px;
  border: none;
}

.login-page__textarea :deep(textarea) {
  min-height: 98px;
}

@media (max-width: 1360px) {
  .login-page {
    gap: 22px;
  }

  .login-page__hero {
    gap: 12px;
    padding: 28px 30px;
  }

  .login-page__process-strip {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }

  .login-page__process-item {
    min-height: 78px;
    padding: 10px 11px;
  }

  .login-page__process-item small {
    font-size: 11px;
    line-height: 1.4;
  }

  .login-page__system-card {
    gap: 8px;
    padding: 14px 16px;
  }

  .login-page__hero-main {
    grid-template-columns: minmax(0, 1fr) minmax(250px, 0.8fr);
    gap: 12px;
  }

  .login-page__hero-copy {
    gap: 12px;
  }

  .login-page__system-card strong {
    font-size: 24px;
  }

  .login-page__title {
    font-size: clamp(34px, 3.8vw, 46px);
  }

  .login-page__description {
    font-size: 14px;
    line-height: 1.65;
  }

  .login-page__highlights {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .login-page__highlight,
  .login-page__highlight:first-child {
    grid-column: auto;
  }

  .login-page__highlight {
    gap: 7px;
    padding: 13px 14px;
    border-radius: 16px;
  }

  .login-page__highlight span {
    display: none;
  }

  .login-page__highlight-list {
    gap: 8px;
  }

  .login-page__highlight-list li {
    font-size: 11px;
  }

  .login-page__coverage {
    gap: 10px;
    padding: 13px 14px;
    border-radius: 18px;
  }

  .login-page__snapshot {
    gap: 10px;
    padding: 13px 14px;
  }

  .login-page__support-grid {
    gap: 10px;
  }

  .login-page__snapshot-grid {
    gap: 8px;
  }

  .login-page__snapshot-item {
    min-height: 66px;
    padding: 10px;
  }

  .login-page__snapshot-item strong {
    font-size: 16px;
  }

  .login-page__snapshot-item small {
    font-size: 10px;
    line-height: 1.35;
  }

  .login-page__coverage-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .login-page__coverage-grid span {
    min-height: 32px;
    padding: 0 6px;
    font-size: 12px;
  }

  .login-page__form-card {
    gap: 14px;
    padding: 28px 28px;
  }

  .login-page__workspace-preview {
    padding: 14px;
  }

  .login-page__auth-paths {
    padding: 14px;
  }

  .login-page__auth-path {
    min-height: 72px;
    padding: 10px;
  }

  .login-page__workspace-item {
    min-height: 76px;
    padding: 12px;
  }
}

@media (max-width: 1360px) and (max-height: 760px) {
  .login-page {
    gap: 18px;
    padding: 20px;
  }

  .login-page__hero,
  .login-page__form-card {
    height: calc(100dvh - 40px);
    min-height: calc(100dvh - 40px);
    max-height: calc(100dvh - 40px);
  }

  .login-page__hero {
    gap: 10px;
    padding: 20px 22px;
  }

  .login-page__process-strip {
    gap: 6px;
  }

  .login-page__process-item {
    min-height: 58px;
    padding: 8px 10px;
  }

  .login-page__process-item strong {
    font-size: 13px;
  }

  .login-page__process-item small {
    display: none;
  }

  .login-page__hero-main {
    gap: 10px;
    grid-template-columns: minmax(0, 1fr) minmax(226px, 0.76fr);
    grid-template-rows: max-content minmax(max-content, 1fr);
  }

  .login-page__hero-copy {
    gap: 10px;
  }

  .login-page__system-card {
    gap: 6px;
    padding: 12px 14px;
  }

  .login-page__system-card strong {
    font-size: 21px;
  }

  .login-page__system-card p {
    font-size: 12px;
    line-height: 1.45;
  }

  .login-page__title {
    font-size: 40px;
    line-height: 1;
  }

  .login-page__description {
    font-size: 13px;
    line-height: 1.48;
  }

  .login-page__support-grid {
    gap: 8px;
  }

  .login-page__snapshot,
  .login-page__coverage {
    gap: 8px;
    padding: 10px 12px;
  }

  .login-page__snapshot-grid,
  .login-page__coverage-grid {
    gap: 6px;
  }

  .login-page__snapshot-item {
    min-height: 44px;
    gap: 2px;
    padding: 7px 8px;
  }

  .login-page__snapshot-item span {
    font-size: 11px;
  }

  .login-page__snapshot-item strong {
    font-size: 14px;
  }

  .login-page__snapshot-item small {
    display: none;
  }

  .login-page__coverage-grid span {
    min-height: 28px;
    font-size: 11px;
  }

  .login-page__highlights {
    gap: 8px;
  }

  .login-page__highlight {
    min-height: 68px;
    gap: 4px;
    padding: 9px 10px;
  }

  .login-page__highlight strong {
    font-size: 13px;
  }

  .login-page__highlight span {
    font-size: 11px;
    line-height: 1.35;
  }

  .login-page__highlight-list {
    gap: 5px;
  }

  .login-page__highlight-list li {
    font-size: 10px;
  }

  .login-page__form-card {
    gap: 12px;
    padding: 22px;
  }
}

@media (max-width: 1180px) {
  .login-page {
    height: 100dvh;
    min-height: 100dvh;
    grid-template-columns: 1fr;
    align-items: start;
    overflow-x: hidden;
    overflow-y: auto;
  }

  .login-page__hero {
    height: auto;
    min-height: auto;
    grid-template-rows: none;
  }

  .login-page__process-strip,
  .login-page__coverage-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .login-page__hero-main,
  .login-page__support-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .login-page__highlights {
    grid-template-columns: 1fr;
  }

  .login-page__highlight:first-child {
    grid-column: auto;
  }

  .login-page__form-card {
    justify-self: stretch;
    width: 100%;
    height: auto;
    min-height: auto;
    max-height: none;
    overflow: visible;
  }
}

@media (max-width: 960px) {
  .login-page {
    padding: 18px;
  }

  .login-page__hero {
    padding: 28px 22px;
  }

  .login-page__system-card {
    width: 100%;
  }

  .login-page__title {
    font-size: 38px;
  }

  .login-page__form-card {
    min-height: auto;
    padding: 26px 20px;
  }

  .login-page__actions {
    grid-template-columns: 1fr;
  }

  .login-page__stepper,
  .login-page__field-grid,
  .login-page__step-actions,
  .login-page__workspace-grid {
    grid-template-columns: 1fr;
  }

  .login-page__step-page {
    min-height: auto;
  }
}

@media (max-width: 720px) {
  .login-page {
    padding: 14px;
  }

  .login-page__hero {
    padding: 24px 18px;
    border-radius: 24px;
  }

  .login-page__system-card {
    padding: 16px;
    border-radius: 20px;
  }

  .login-page__system-card strong {
    font-size: 20px;
  }

  .login-page__description {
    font-size: 14px;
  }

  .login-page__highlight {
    padding: 18px;
    border-radius: 18px;
  }

  .login-page__form-card {
    padding: 22px 16px;
    border-radius: 24px;
  }
}
</style>
