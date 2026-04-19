<script setup lang="ts">
import PageHeader from "@/components/common/PageHeader.vue";
import MetricCard from "@/components/common/MetricCard.vue";
import { useDashboardOverview } from "@/composables/useDashboardOverview";

const { loading, error, summary, trendItems, defectItems, refresh } = useDashboardOverview();
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Analytics"
      title="统计分析"
      description="统计页和仪表盘共用同一套统计接口与组合式逻辑，后续可以直接扩展 ECharts，而不需要重写数据层。"
    />

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      :title="error"
    />

    <div v-if="summary" class="page-grid three-col">
      <MetricCard
        label="总检测量"
        :value="String(summary.totalCount)"
        hint="来自 summary 接口"
      />
      <MetricCard
        label="良率"
        :value="`${Math.round(summary.passRate * 100)}%`"
        hint="当前使用最终结果计算"
        accent="success"
      />
      <MetricCard
        label="待审核"
        :value="String(summary.pendingReviewCount)"
        hint="可对接人工审核工作台"
        accent="warning"
      />
    </div>

    <div class="page-grid two-col">
      <section class="app-panel stats-section">
        <div class="stats-section__header">
          <strong>近 7 日记录</strong>
          <ElButton text @click="refresh" :loading="loading">刷新</ElButton>
        </div>
        <ElTable :data="trendItems" empty-text="暂无趋势数据">
          <ElTableColumn prop="date" label="日期" min-width="140" />
          <ElTableColumn prop="totalCount" label="总数" min-width="80" />
          <ElTableColumn prop="goodCount" label="良品" min-width="80" />
          <ElTableColumn prop="badCount" label="坏品" min-width="80" />
        </ElTable>
      </section>

      <section class="app-panel stats-section">
        <div class="stats-section__header">
          <strong>缺陷统计</strong>
        </div>
        <ElTable :data="defectItems" empty-text="暂无缺陷数据">
          <ElTableColumn prop="defectType" label="缺陷类型" min-width="180" />
          <ElTableColumn prop="count" label="数量" min-width="90" />
        </ElTable>
      </section>
    </div>
  </div>
</template>

<style scoped>
.stats-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.stats-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
</style>
