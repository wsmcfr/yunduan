<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import AppShell from "@/components/layout/AppShell.vue";

const route = useRoute();

/**
 * 根据当前路由判断是否显示主应用框架。
 * 登录页使用独立视觉布局，其余页面复用统一后台壳。
 */
const shouldUseShell = computed(() => route.meta.useShell !== false);
</script>

<template>
  <AppShell v-if="shouldUseShell">
    <RouterView />
  </AppShell>
  <RouterView v-else />
</template>
