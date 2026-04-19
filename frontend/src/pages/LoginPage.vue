<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Lock, User } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import PageHeader from "@/components/common/PageHeader.vue";
import { useAuthStore } from "@/stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const loading = ref(false);

/**
 * 登录表单状态。
 * 默认填入本地联调账号，方便你直接体验从登录到后台首页的完整流程。
 */
const formState = reactive({
  username: "admin",
  password: "admin123",
});

async function handleLogin(): Promise<void> {
  loading.value = true;

  try {
    await authStore.login(formState.username, formState.password);
    ElMessage.success("登录成功");

    const redirectTarget =
      typeof route.query.redirect === "string" && route.query.redirect.length > 0
        ? route.query.redirect
        : "/dashboard";

    await router.push(redirectTarget);
  } catch (caughtError) {
    ElMessage.error(caughtError instanceof Error ? caughtError.message : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-page__hero">
      <span class="login-page__eyebrow">Industrial Defect Detection</span>
      <h1 class="login-page__title">云端检测系统</h1>
      <p class="login-page__description">
        这一版前端先把页面框架、认证流程和后台导航跑起来，后续你可以继续往里接
        COS 图片、人工审核和 AI 复核流程。
      </p>

      <div class="login-page__highlights">
        <div class="login-page__highlight app-panel">
          <strong>本地后端已打通</strong>
          <span>默认代理到 `127.0.0.1:8000`</span>
        </div>
        <div class="login-page__highlight app-panel">
          <strong>当前默认账号</strong>
          <span>`admin / admin123`</span>
        </div>
      </div>
    </section>

    <section class="login-page__form-card app-panel">
      <PageHeader
        eyebrow="Access"
        title="登录控制台"
        description="输入管理员账号后进入云端检测后台。"
      />

      <ElForm class="login-page__form" label-position="top" @submit.prevent="handleLogin">
        <ElFormItem label="用户名">
          <ElInput v-model="formState.username" :prefix-icon="User" placeholder="请输入用户名" />
        </ElFormItem>

        <ElFormItem label="密码">
          <ElInput
            v-model="formState.password"
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
          :loading="loading"
          size="large"
        >
          进入系统
        </ElButton>
      </ElForm>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
  gap: 30px;
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
  max-width: 640px;
  color: var(--app-text-secondary);
  font-size: 17px;
  line-height: 1.8;
}

.login-page__highlights {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 26px;
}

.login-page__highlight {
  display: grid;
  gap: 8px;
  padding: 20px;
}

.login-page__highlight span {
  color: var(--app-text-secondary);
  font-size: 14px;
}

.login-page__form-card {
  align-self: center;
  padding: 28px;
}

.login-page__form {
  margin-top: 24px;
}

.login-page__submit {
  width: 100%;
  margin-top: 10px;
  border: none;
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

  .login-page__highlights {
    grid-template-columns: 1fr;
  }
}
</style>
