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

import ContestAiLogo from "@/components/branding/ContestAiLogo.vue";
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
      <div class="login-page__contest">
        <p class="login-page__contest-title">第九届嵌入式芯片与系统设计竞赛</p>
        <ContestAiLogo class="login-page__contest-logo" />
      </div>

      <span class="login-page__eyebrow">Industrial Defect Detection</span>
      <h1 class="login-page__title">云端检测系统</h1>
      <p class="login-page__description">
        认证入口已经切换为正式多租户模式。普通成员通过邀请码加入现有公司，新公司负责人通过审批创建独立空间；
        登录态由服务端 `HttpOnly Cookie` 托管，密码与密钥等敏感信息都只留在后端。
      </p>

      <div class="login-page__highlights">
        <div class="login-page__highlight app-panel">
          <strong>双注册路径</strong>
          <span>普通成员走邀请码入司，新公司负责人走平台审批建公司。</span>
        </div>
        <div class="login-page__highlight app-panel">
          <strong>服务端会话</strong>
          <span>浏览器不再保存可读 Token，刷新后仍可恢复登录状态。</span>
        </div>
        <div class="login-page__highlight app-panel">
          <strong>密码加固</strong>
          <span>采用慢哈希、随机盐与服务端 pepper，降低数据库泄露后的破解风险。</span>
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

          <ElForm class="login-page__form" label-position="top" @submit.prevent="handleLogin">
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
              class="login-page__submit"
              color="var(--app-primary)"
              native-type="submit"
              :loading="loginLoading"
              size="large"
            >
              进入系统
            </ElButton>
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
            <ElAlert
              class="login-page__alert login-page__alert--inline"
              title="请选择注册方式"
              type="info"
              :closable="false"
              description="邀请码路径适合加入现有公司；管理员申请路径适合新建全新的独立公司空间。"
            />

            <div class="login-page__mode-switch">
              <ElRadioGroup v-model="registerFormState.registerMode" size="large">
                <ElRadioButton value="invite_join">邀请码加入公司</ElRadioButton>
                <ElRadioButton value="company_admin_request">申请新公司管理员</ElRadioButton>
              </ElRadioGroup>
              <p class="login-page__mode-note">{{ registerModeSummary }}</p>
            </div>

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

            <ElFormItem label="邮箱">
              <ElInput
                v-model="registerFormState.email"
                :prefix-icon="Message"
                placeholder="请输入可接收邮件的邮箱"
              />
            </ElFormItem>

            <ElFormItem v-if="isInviteJoinMode" label="公司邀请码">
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

              <ElFormItem label="申请备注">
                <ElInput
                  v-model="registerFormState.companyNote"
                  class="login-page__textarea"
                  type="textarea"
                  :rows="3"
                  resize="vertical"
                  placeholder="可填写业务场景、设备规模或其他审批说明"
                />
              </ElFormItem>
            </template>

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

            <p class="login-page__policy">{{ runtimeOptions.passwordPolicyHint }}</p>

            <ElButton
              class="login-page__submit"
              color="var(--app-primary)"
              native-type="submit"
              :loading="registerLoading"
              size="large"
            >
              {{ registerSubmitText }}
            </ElButton>
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
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(380px, 560px);
  gap: 28px;
  min-height: 100vh;
  padding: 28px;
  max-width: 1520px;
  margin: 0 auto;
  position: relative;
  align-items: stretch;
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
  align-content: center;
  gap: 22px;
  padding: clamp(34px, 4vw, 52px);
  border: 1px solid rgba(149, 184, 223, 0.14);
  border-radius: 34px;
  background:
    radial-gradient(circle at top right, rgba(74, 212, 154, 0.12), transparent 34%),
    radial-gradient(circle at bottom left, rgba(93, 151, 242, 0.14), transparent 36%),
    linear-gradient(145deg, rgba(11, 25, 43, 0.92), rgba(10, 22, 38, 0.82));
  overflow: hidden;
}

.login-page__hero::before,
.login-page__hero::after {
  content: "";
  position: absolute;
  border: 1px solid rgba(149, 184, 223, 0.08);
  border-radius: 28px;
  pointer-events: none;
}

.login-page__hero::before {
  top: 18px;
  right: 18px;
  width: 220px;
  height: 120px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent);
}

.login-page__hero::after {
  left: -72px;
  bottom: -92px;
  width: 260px;
  height: 260px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(127, 228, 208, 0.08), transparent 70%);
}

.login-page__contest {
  display: grid;
  gap: 12px;
  width: min(100%, 640px);
  padding: 18px 20px;
  border: 1px solid rgba(149, 184, 223, 0.1);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(10px);
}

.login-page__contest-title {
  margin: 0;
  color: #e4eef8;
  font-size: clamp(22px, 2.6vw, 32px);
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.2;
}

.login-page__contest-logo {
  display: block;
  width: min(100%, 420px);
  filter: drop-shadow(0 16px 30px rgba(8, 18, 37, 0.24));
}

.login-page__eyebrow {
  color: var(--app-primary);
  letter-spacing: 0.18em;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.login-page__title {
  margin: 0;
  max-width: 720px;
  font-size: clamp(50px, 5.5vw, 78px);
  line-height: 0.92;
  text-wrap: balance;
}

.login-page__description {
  max-width: 660px;
  color: var(--app-text-secondary);
  font-size: 16px;
  line-height: 1.95;
}

.login-page__highlights {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 6px;
}

.login-page__highlight {
  display: grid;
  gap: 10px;
  padding: 20px 22px;
  border-radius: 22px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.015)),
    rgba(8, 19, 33, 0.3);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.login-page__highlight:first-child {
  grid-column: 1 / -1;
}

.login-page__highlight span {
  color: var(--app-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.login-page__form-card {
  position: relative;
  align-self: center;
  justify-self: end;
  width: min(100%, 560px);
  min-height: min(820px, calc(100vh - 56px));
  padding: 34px 32px;
  border-radius: 30px;
  border: 1px solid rgba(149, 184, 223, 0.14);
  background:
    radial-gradient(circle at top center, rgba(127, 228, 208, 0.08), transparent 30%),
    linear-gradient(180deg, rgba(13, 28, 48, 0.94), rgba(10, 22, 38, 0.92));
  overflow: hidden;
}

.login-page__form-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
  background: linear-gradient(90deg, rgba(127, 228, 208, 0.96), rgba(93, 151, 242, 0.92));
}

.login-page__tabs {
  margin-top: 18px;
}

.login-page__form {
  margin-top: 18px;
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
  margin-bottom: 18px;
  padding: 16px 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
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
    grid-template-columns: minmax(0, 1fr) minmax(360px, 500px);
    gap: 22px;
  }

  .login-page__hero {
    padding: 34px 30px;
  }

  .login-page__title {
    font-size: clamp(46px, 5vw, 64px);
  }
}

@media (max-width: 1180px) {
  .login-page {
    grid-template-columns: 1fr;
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
    min-height: auto;
  }
}

@media (max-width: 960px) {
  .login-page {
    padding: 18px;
  }

  .login-page__hero {
    padding: 28px 22px;
  }

  .login-page__contest {
    width: 100%;
  }

  .login-page__contest-logo {
    width: min(100%, 360px);
  }

  .login-page__title {
    font-size: 42px;
  }

  .login-page__form-card {
    min-height: auto;
    padding: 26px 20px;
  }

  .login-page__actions {
    grid-template-columns: 1fr;
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

  .login-page__contest {
    padding: 16px;
    border-radius: 20px;
  }

  .login-page__contest-title {
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
