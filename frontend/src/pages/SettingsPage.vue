<script setup lang="ts">
import PageHeader from "@/components/common/PageHeader.vue";
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Settings"
      title="系统设置"
      description="设置页当前先作为运维占位页面，后续适合放后端地址、COS 连通状态、AI 复核供应商开关和用户权限管理。"
    />

    <div class="page-grid two-col">
      <section class="app-panel settings-card">
        <strong>当前前端约定</strong>
        <ElDescriptions :column="1" border>
          <ElDescriptionsItem label="前端地址">http://127.0.0.1:5173</ElDescriptionsItem>
          <ElDescriptionsItem label="后端代理">http://127.0.0.1:8000</ElDescriptionsItem>
          <ElDescriptionsItem label="鉴权方式">JWT + Pinia</ElDescriptionsItem>
          <ElDescriptionsItem label="对象存储">腾讯云 COS 预留</ElDescriptionsItem>
        </ElDescriptions>
      </section>

      <section class="app-panel settings-card">
        <strong>下一步建议</strong>
        <ElTimeline>
          <ElTimelineItem timestamp="Step 1" type="primary">
            接入创建零件、创建设备和新增记录表单
          </ElTimelineItem>
          <ElTimelineItem timestamp="Step 2" type="success">
            接记录详情页中的图片预览与人工审核提交流程
          </ElTimelineItem>
          <ElTimelineItem timestamp="Step 3" type="warning">
            加入 COS 上传状态和 AI 复核结果展示
          </ElTimelineItem>
        </ElTimeline>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-card {
  display: grid;
  gap: 18px;
  padding: 22px;
}
</style>
