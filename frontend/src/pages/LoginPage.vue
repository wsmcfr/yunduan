<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Lock, Message, User } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import { fetchAuthRuntimeOptionsRequest, forgotPasswordRequest, resetPasswordRequest } from "@/services/api/auth";
import { mapAuthRuntimeOptionsDto } from "@/services/mappers/commonMappers";
import { routeNames } from "@/router/routes";
import { useAuthStore } from "@/stores/auth";
import type { AuthRuntimeOptions } from "@/types/models";

type PublicAuthPanel = "login" | "register" | "forgot";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

/**
 * 认证页运行时能力。
 * 即使该接口暂时失败，也保留一份安全的默认值，避免页面完全不可用。
 */
const runtimeOptions = ref<AuthRuntimeOptions>({
  registrationEnabled: true,
  passwordResetEnabled: false,
  passwordPolicyHint: "密码需为 8-128 位，并至少包含大写字母、小写字母、数字、符号中的三类。",
});

// 公共认证区只在登录 / 注册 / 找回密码三块之间切换。
const activePanel = ref<PublicAuthPanel>("login");

// 各个表单的提交态拆开维护，避免一个流程阻塞另一个流程。
const loginLoading = ref(false);
const registerLoading = ref(false);
const forgotLoading = ref(false);
const resetLoading = ref(false);

/**
 * 登录表单状态。
 * 这里只保留用户输入，不再预填真实或假演示账号。
 */
const loginFormState = reactive({
  account: "",
  password: "",
});

/**
 * 注册表单状态。
 * 展示名、邮箱和密码都在前端做一次基础校验，减少无意义请求。
 */
const registerFormState = reactive({
  username: "",
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
});

/**
 * 忘记密码表单状态。
 * 找回流程统一按邮箱发起，避免公开接口返回账号是否存在。
 */
const forgotFormState = reactive({
  email: "",
});

/**
 * 重置密码表单状态。
 * token 可以来自邮件链接，也允许人工粘贴。
 */
const resetFormState = reactive({
  token: "",
  newPassword: "",
  confirmPassword: "",
});

// 当前是否处于“邮件链接跳转后的重置密码视图”。
const isResetRoute = computed(() => route.name === routeNames.resetPassword);

/**
 * 读取认证运行时能力。
 * 这里失败时不打断页面，只保留默认值继续渲染。
 */
async function loadRuntimeOptions(): Promise<void> {
  try {
    const response = await fetchAuthRuntimeOptionsRequest();
    runtimeOptions.value = mapAuthRuntimeOptionsDto(response);
  } catch {
    // 认证配置接口只是辅助信息；失败时不影响登录和重置等主流程继续尝试。
  }
}

/**
 * 解析登录成功后的目标跳转地址。
 */
function resolveRedirectTarget(): string {
  return typeof route.query.redirect === "string" && route.query.redirect.length > 0
    ? route.query.redirect
    : "/dashboard";
}

/**
 * 清理登录表单中的敏感密码字段，减少前端内存中残留时间。
 */
function clearLoginSensitiveFields(): void {
  loginFormState.password = "";
}

/**
 * 清理注册表单中的敏感密码字段。
 */
function clearRegisterSensitiveFields(): void {
  registerFormState.password = "";
  registerFormState.confirmPassword = "";
}

/**
 * 清理重置密码表单中的敏感字段。
 * 某些场景下允许保留 token，方便用户重新提交。
 */
function clearResetSensitiveFields(preserveToken = true): void {
  if (!preserveToken) {
    resetFormState.token = "";
  }
  resetFormState.newPassword = "";
  resetFormState.confirmPassword = "";
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
 * 处理注册。
 */
async function handleRegister(): Promise<void> {
  if (!runtimeOptions.value.registrationEnabled) {
    ElMessage.warning("当前环境未开放自助注册。");
    return;
  }
  if (
    !registerFormState.username.trim()
    || !registerFormState.displayName.trim()
    || !registerFormState.email.trim()
    || !registerFormState.password
  ) {
    ElMessage.warning("请完整填写注册信息。");
    return;
  }
  if (registerFormState.password !== registerFormState.confirmPassword) {
    ElMessage.warning("两次输入的密码不一致。");
    return;
  }

  registerLoading.value = true;
  try {
    await authStore.register({
      username: registerFormState.username,
      displayName: registerFormState.displayName,
      email: registerFormState.email,
      password: registerFormState.password,
    });
    clearRegisterSensitiveFields();
    ElMessage.success("注册成功，已自动登录。");
    await router.push(resolveRedirectTarget());
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
 * 把链接里的重置 token 同步到表单。
 */
watch(
  () => route.query.token,
  (tokenValue) => {
    resetFormState.token = typeof tokenValue === "string" ? tokenValue.trim() : "";
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
      <span class="login-page__eyebrow">Industrial Defect Detection</span>
      <h1 class="login-page__title">云端检测系统</h1>
      <p class="login-page__description">
        这一版认证已经不再是临时占位页，而是正式的登录、注册和密码找回入口。
        登录态由服务端 `HttpOnly Cookie` 托管，密码使用慢哈希与服务端 pepper 加固，其它敏感配置继续留在后端。
      </p>

      <div class="login-page__highlights">
        <div class="login-page__highlight app-panel">
          <strong>服务端会话</strong>
          <span>浏览器不再保存可读 Token，刷新后仍可恢复登录状态。</span>
        </div>
        <div class="login-page__highlight app-panel">
          <strong>密码加固</strong>
          <span>采用慢哈希、随机盐与服务端 pepper，降低数据库泄露后的破解风险。</span>
        </div>
        <div class="login-page__highlight app-panel">
          <strong>邮件找回</strong>
          <span>支持一次性重置令牌，数据库里只保留令牌哈希而不是明文链接。</span>
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
            : '登录、注册和密码找回都统一在这里处理。'
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

          <ElForm v-else class="login-page__form" label-position="top" @submit.prevent="handleRegister">
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
              创建账号
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

          <ElForm
            v-else
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
        </ElTabPane>
      </ElTabs>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(400px, 0.82fr);
  gap: 32px;
  min-height: 100vh;
  padding: 32px;
}

.login-page__hero {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 32px;
}

.login-page__eyebrow {
  color: var(--app-primary);
  letter-spacing: 0.18em;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.login-page__title {
  margin: 18px 0 14px;
  font-size: 64px;
  line-height: 0.95;
}

.login-page__description {
  max-width: 680px;
  color: var(--app-text-secondary);
  font-size: 17px;
  line-height: 1.9;
}

.login-page__highlights {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 28px;
}

.login-page__highlight {
  display: grid;
  gap: 8px;
  padding: 20px;
}

.login-page__highlight span {
  color: var(--app-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.login-page__form-card {
  align-self: center;
  padding: 28px;
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

.login-page__secondary,
.login-page__submit {
  width: 100%;
  margin-top: 10px;
  border: none;
}

@media (max-width: 1180px) {
  .login-page__highlights {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .login-page {
    grid-template-columns: 1fr;
    padding: 18px;
  }

  .login-page__hero {
    padding: 12px 0;
  }

  .login-page__title {
    font-size: 42px;
  }

  .login-page__actions {
    grid-template-columns: 1fr;
  }
}
</style>
