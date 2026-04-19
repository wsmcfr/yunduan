<script setup lang="ts">
import { computed } from "vue";

import MetricCard from "@/components/common/MetricCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useDashboardOverview } from "@/composables/useDashboardOverview";

const { loading, error, summary, trendItems, defectItems, refresh } = useDashboardOverview();

const latestTrend = computed(() => trendItems.value[trendItems.value.length - 1] ?? null);
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Overview"
      title="比赛项目总览"
      description="把检测记录、设备状态和审核趋势先统一收进一个主视图。当前仪表盘直接读取本地后端统计接口。"
    />

    <ElAlert
      v-if="error"
      type="error"
      :closable="false"
      :title="error"
      show-icon
    />

    <div v-if="summary" class="page-grid three-col">
      <MetricCard
        label="检测总量"
        :value="String(summary.totalCount)"
        hint="累计进入检测主流程的记录数"
        accent="primary"
      />
      <MetricCard
        label="良品数量"
        :value="String(summary.goodCount)"
        hint="人工审核优先，否则使用模型结果"
        accent="success"
      />
      <MetricCard
        label="不良数量"
        :value="String(summary.badCount)"
        hint="建议后续再细分成缺陷类别统计"
        accent="danger"
      />
      <MetricCard
        label="待审核"
        :value="String(summary.pendingReviewCount)"
        hint="适合后续接人工审核工作台"
        accent="warning"
      />
      <MetricCard
        label="已审核"
        :value="String(summary.reviewedCount)"
        hint="已进入人工复核闭环的记录"
        accent="info"
      />
      <MetricCard
        label="良率"
        :value="`${Math.round(summary.passRate * 100)}%`"
        hint="当前按最终生效结果计算"
        accent="success"
      />
    </div>

    <div class="page-grid two-col">
      <section class="app-panel dashboard-section">
        <div class="dashboard-section__header">
          <strong>近 7 日趋势</strong>
          <ElButton text @click="refresh" :loading="loading">刷新数据</ElButton>
        </div>

        <ElTable :data="trendItems" empty-text="暂无趋势数据">
          <ElTableColumn prop="date" label="日期" min-width="140" />
          <ElTableColumn prop="totalCount" label="总数" min-width="90" />
          <ElTableColumn prop="goodCount" label="良品" min-width="90" />
          <ElTableColumn prop="badCount" label="不良" min-width="90" />
          <ElTableColumn prop="uncertainCount" label="待确认" min-width="110" />
        </ElTable>
      </section>

      <section class="app-panel dashboard-section">
        <div class="dashboard-section__header">
          <strong>缺陷分布</strong>
          <span class="muted-text">先用表格占位，后续可以换柱状图或环图</span>
        </div>

        <ElTable :data="defectItems" empty-text="暂无缺陷分布数据">
          <ElTableColumn prop="defectType" label="缺陷类型" min-width="180" />
          <ElTableColumn prop="count" label="数量" min-width="90" />
        </ElTable>
      </section>
    </div>

    <section class="app-panel dashboard-section">
      <div class="dashboard-section__header">
        <strong>当前页面说明</strong>
      </div>

      <ElDescriptions :column="2" border>
        <ElDescriptionsItem label="当前状态">
          {{ loading ? "加载中" : "已连接后端统计接口" }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="最近趋势日期">
          {{ latestTrend?.date ?? "暂无" }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="下一步建议">
          接记录列表、设备概览、审核入口
        </ElDescriptionsItem>
        <ElDescriptionsItem label="后端接口">
          `/api/v1/statistics/*`
        </ElDescriptionsItem>
      </ElDescriptions>
    </section>
  </div>
</template>

<style scoped>
.dashboard-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.dashboard-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
