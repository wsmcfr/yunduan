<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import MetricCard from "@/components/common/MetricCard.vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useDashboardOverview } from "@/composables/useDashboardOverview";
import { routeNames } from "@/router/routes";
import { formatDateTime } from "@/utils/format";

const router = useRouter();
const DASHBOARD_TREND_ROW_LIMIT = 7;

/**
 * 仪表盘分页工作区。
 * 首页内容较多，这里明确拆成三页，避免把总览、趋势和入口全部堆成一个超长页面。
 */
type DashboardWorkspacePage = "summary" | "risk" | "actions";

/**
 * 仪表盘分页导航配置。
 * 每一页只承担一个阅读任务，让用户更容易判断“这一页该看什么”。
 */
const DASHBOARD_WORKSPACE_PAGE_OPTIONS: Array<{
  name: DashboardWorkspacePage;
  title: string;
  description: string;
}> = [
  {
    name: "summary",
    title: "核心总览",
    description: "看当前窗口最关键的指标和焦点对象。",
  },
  {
    name: "risk",
    title: "趋势风险",
    description: "看近期趋势、缺陷结构和审核状态。",
  },
  {
    name: "actions",
    title: "入口建议",
    description: "看风险排行、样本图库入口和下一步建议。",
  },
];

const {
  loading,
  error,
  overview,
  summary,
  trendItems,
  defectItems,
  reviewStatusItems,
  partRiskItems,
  deviceRiskItems,
  sampleGallery,
  keyFindings,
  riskRecordCount,
  reviewCompletionRate,
  latestTrend,
  topDefect,
  topPartRisk,
  topDeviceRisk,
  refresh,
} = useDashboardOverview();

/**
 * 把比例统一格式化成百分比。
 * 仪表盘多个区域都会显示良率、审核完成率等比例值，这里统一收口避免口径漂移。
 */
function formatPercent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

/**
 * 生成相对宽度百分比，供排行条和缺陷条形宽度复用。
 * 当基准值为空或为 0 时统一返回 0，避免在样式里出现 `NaN%`。
 */
function resolveRelativeWidth(value: number, maxValue: number): string {
  if (maxValue <= 0) {
    return "0%";
  }
  return `${Math.max((value / maxValue) * 100, 6).toFixed(1)}%`;
}

/**
 * 导航到目标页面。
 * 仪表盘只做总览，不承载所有细节，重要信息都应该能一键跳到对应工作页继续处理。
 */
function navigateTo(routeName: string): void {
  void router.push({ name: routeName });
}

/**
 * 顶部指标卡配置。
 * 这里强调“首页最先要看的六个量”，让用户进入系统后先判断规模、风险和闭环进度。
 */
const metricCards = computed(() => {
  if (!summary.value) {
    return [];
  }

  return [
    {
      label: "检测总量",
      value: String(summary.value.totalCount),
      hint: "当前窗口内全部检测记录",
      accent: "primary" as const,
    },
    {
      label: "风险记录",
      value: String(riskRecordCount.value),
      hint: `不良 ${summary.value.badCount} / 待确认 ${summary.value.uncertainCount}`,
      accent: "danger" as const,
    },
    {
      label: "审核完成率",
      value: formatPercent(reviewCompletionRate.value),
      hint: `已审核 ${summary.value.reviewedCount} / 待审核 ${summary.value.pendingReviewCount}`,
      accent: "info" as const,
    },
    {
      label: "当前良率",
      value: formatPercent(summary.value.passRate),
      hint: `良品 ${summary.value.goodCount} 条`,
      accent: "success" as const,
    },
    {
      label: "样本图片",
      value: String(sampleGallery.value?.totalImageCount ?? 0),
      hint: `覆盖 ${sampleGallery.value?.totalPartCount ?? 0} 个分类`,
      accent: "warning" as const,
    },
    {
      label: "活跃日期",
      value: latestTrend.value?.date ?? "暂无",
      hint: latestTrend.value
        ? `当日总量 ${latestTrend.value.totalCount}，不良 ${latestTrend.value.badCount}`
        : "当前窗口暂无活跃趋势点",
      accent: "primary" as const,
    },
  ];
});

/**
 * 顶部焦点标签。
 * 这里不堆太多字段，只保留用户进入首页后最值得先关注的三条线索。
 */
const focusBadges = computed(() => [
  {
    label: "最集中缺陷",
    value: topDefect.value ? `${topDefect.value.defectType} · ${topDefect.value.count} 条` : "暂无",
  },
  {
    label: "风险最高零件",
    value: topPartRisk.value
      ? `${topPartRisk.value.partName} / ${topPartRisk.value.partCode}`
      : "暂无",
  },
  {
    label: "风险最高设备",
    value: topDeviceRisk.value
      ? `${topDeviceRisk.value.deviceName} / ${topDeviceRisk.value.deviceCode}`
      : "暂无",
  },
]);

/**
 * 趋势区中每一行的组成条。
 * 它不追求精确图表，而是帮助用户快速看出某一天是“量大”还是“风险高”。
 */
const trendRows = computed(() => {
  const maxTotalCount = Math.max(...trendItems.value.map((item) => item.totalCount), 0);

  return trendItems.value.map((item) => {
    const compositionBase = Math.max(item.totalCount, 1);
    return {
      ...item,
      totalWidth: resolveRelativeWidth(item.totalCount, maxTotalCount),
      goodWidth: `${((item.goodCount / compositionBase) * 100).toFixed(1)}%`,
      badWidth: `${((item.badCount / compositionBase) * 100).toFixed(1)}%`,
      uncertainWidth: `${((item.uncertainCount / compositionBase) * 100).toFixed(1)}%`,
    };
  });
});

/**
 * 缺陷列表转成适合首页展示的 Top 列表。
 * 仪表盘只保留前四项，详细分布交给统计分析页。
 */
const defectRows = computed(() => {
  const visibleItems = defectItems.value.slice(0, 4);
  const maxCount = Math.max(...visibleItems.map((item) => item.count), 0);

  return visibleItems.map((item) => ({
    ...item,
    width: resolveRelativeWidth(item.count, maxCount),
  }));
});

/**
 * 仪表盘趋势区只保留最近几天，避免首页因为趋势明细过多被拉成超长页面。
 * 更完整的趋势追查交给统计分析页处理。
 */
const visibleTrendRows = computed(() => trendRows.value.slice(-DASHBOARD_TREND_ROW_LIMIT));

/**
 * 如果统计窗口比首页展示的趋势天数更多，就在趋势区底部补一个提示。
 */
const hiddenTrendRowCount = computed(() =>
  Math.max(trendRows.value.length - visibleTrendRows.value.length, 0),
);

/**
 * 结果结构卡片。
 * 比起纯表格，这种小卡片更适合首页快速浏览。
 */
const resultCards = computed(() => {
  const currentOverview = overview.value;
  const currentSummary = summary.value;
  if (!currentOverview || !currentSummary) {
    return [];
  }

  return currentOverview.resultDistribution.map((item) => {
    const label = item.result === "good" ? "良品" : item.result === "bad" ? "不良" : "待确认";
    const accent = item.result === "good" ? "success" : item.result === "bad" ? "danger" : "warning";
    return {
      label,
      value: item.count,
      ratio: currentSummary.totalCount > 0 ? formatPercent(item.count / currentSummary.totalCount) : "0%",
      accent,
    };
  });
});

/**
 * 审核状态摘要。
 * 这里把状态映射成视觉标签，避免首页出现一堆英文/枚举值。
 */
const reviewCards = computed(() => {
  return reviewStatusItems.value.map((item) => {
    const label = item.reviewStatus === "reviewed"
      ? "已审核"
      : item.reviewStatus === "ai_reserved"
        ? "AI 预留"
        : "待审核";
    const accent = item.reviewStatus === "reviewed"
      ? "success"
      : item.reviewStatus === "ai_reserved"
        ? "info"
        : "warning";
    return {
      label,
      value: item.count,
      accent,
    };
  });
});

/**
 * 零件与设备排行条。
 * 首页保留前四项即可，真正的明细仍建议进入统计分析页查看。
 */
const topPartRows = computed(() => {
  const visibleItems = partRiskItems.value.slice(0, 4);
  const maxRiskCount = Math.max(...visibleItems.map((item) => item.badCount + item.uncertainCount), 0);

  return visibleItems.map((item) => ({
    ...item,
    riskCount: item.badCount + item.uncertainCount,
    width: resolveRelativeWidth(item.badCount + item.uncertainCount, maxRiskCount),
  }));
});

const topDeviceRows = computed(() => {
  const visibleItems = deviceRiskItems.value.slice(0, 4);
  const maxRiskCount = Math.max(...visibleItems.map((item) => item.badCount + item.uncertainCount), 0);

  return visibleItems.map((item) => ({
    ...item,
    riskCount: item.badCount + item.uncertainCount,
    width: resolveRelativeWidth(item.badCount + item.uncertainCount, maxRiskCount),
  }));
});

/**
 * 图库摘要区的说明文字。
 */
const latestUploadText = computed(() => {
  return sampleGallery.value?.latestUploadedAt
    ? formatDateTime(sampleGallery.value.latestUploadedAt)
    : "暂无上传记录";
});

/**
 * 当前仪表盘工作区页码。
 */
const activeWorkspacePage = ref<DashboardWorkspacePage>("summary");

/**
 * 当前页码索引与配置。
 * 顶部导航和底部翻页按钮复用同一套状态，避免页码不同步。
 */
const activeWorkspacePageIndex = computed(() =>
  Math.max(
    DASHBOARD_WORKSPACE_PAGE_OPTIONS.findIndex((item) => item.name === activeWorkspacePage.value),
    0,
  ),
);

const activeWorkspacePageConfig = computed(() =>
  DASHBOARD_WORKSPACE_PAGE_OPTIONS[activeWorkspacePageIndex.value]
    ?? DASHBOARD_WORKSPACE_PAGE_OPTIONS[0],
);

/**
 * 直接切换仪表盘分页。
 */
function goToWorkspacePage(nextPage: DashboardWorkspacePage): void {
  activeWorkspacePage.value = nextPage;
}

/**
 * 按顺序切换到上一页或下一页。
 */
function stepWorkspacePage(direction: -1 | 1): void {
  const nextIndex = Math.min(
    Math.max(activeWorkspacePageIndex.value + direction, 0),
    DASHBOARD_WORKSPACE_PAGE_OPTIONS.length - 1,
  );
  activeWorkspacePage.value = DASHBOARD_WORKSPACE_PAGE_OPTIONS[nextIndex]?.name ?? "summary";
}
</script>

<template>
  <div class="page-grid dashboard-page">
    <PageHeader
      eyebrow="Overview"
      title="比赛项目总览"
      description="首页不再只放几个占位表格，而是把当前窗口的检测规模、风险热点、审核闭环和图库覆盖统一放到一个总览页里。需要深入追查时，再进入统计分析、样本图库或检测记录继续处理。"
    />

    <ElAlert
      v-if="error"
      type="error"
      :closable="false"
      :title="error"
      show-icon
    />

    <template v-else-if="summary">
      <section class="app-panel dashboard-pager">
        <div class="dashboard-pager__header">
          <div>
            <strong>分页总览</strong>
            <p class="muted-text">
              首页现在拆成三页：先看核心总览，再看趋势风险，最后看入口建议。每一页都限制在可控高度内，不再把全部模块堆成超长页面。
            </p>
          </div>
          <ElTag effect="dark" round type="info">
            第 {{ activeWorkspacePageIndex + 1 }} / {{ DASHBOARD_WORKSPACE_PAGE_OPTIONS.length }} 页
          </ElTag>
        </div>

        <div class="dashboard-pager__grid">
          <button
            v-for="(item, index) in DASHBOARD_WORKSPACE_PAGE_OPTIONS"
            :key="item.name"
            type="button"
            class="dashboard-pager__item"
            :class="{ 'dashboard-pager__item--active': activeWorkspacePage === item.name }"
            @click="goToWorkspacePage(item.name)"
          >
            <span class="dashboard-pager__item-index">0{{ index + 1 }}</span>
            <strong>{{ item.title }}</strong>
            <span>{{ item.description }}</span>
          </button>
        </div>

        <div class="dashboard-pager__footer">
          <div>
            <strong>{{ activeWorkspacePageConfig.title }}</strong>
            <p class="muted-text">{{ activeWorkspacePageConfig.description }}</p>
          </div>
          <div class="dashboard-pager__actions">
            <ElButton
              plain
              :disabled="activeWorkspacePageIndex <= 0"
              @click="stepWorkspacePage(-1)"
            >
              上一页
            </ElButton>
            <ElButton
              type="primary"
              plain
              :disabled="activeWorkspacePageIndex >= DASHBOARD_WORKSPACE_PAGE_OPTIONS.length - 1"
              @click="stepWorkspacePage(1)"
            >
              下一页
            </ElButton>
          </div>
        </div>
      </section>

      <div class="dashboard-workspace-stage">
        <div
          class="dashboard-workspace-page"
          :class="{ 'dashboard-workspace-page--active': activeWorkspacePage === 'summary' }"
          data-workspace-page="summary"
        >
          <section class="app-panel dashboard-hero">
            <div class="dashboard-hero__copy">
              <span class="dashboard-hero__eyebrow">Command Overview</span>
              <h2>当前窗口最值得先看的三件事</h2>
              <p class="muted-text">
                先看风险是否集中，再决定去统计分析页深挖，还是直接去记录页做人工复核。
              </p>
            </div>

            <div class="dashboard-hero__actions">
              <ElButton :loading="loading" @click="refresh">刷新总览</ElButton>
              <ElButton plain @click="navigateTo(routeNames.statistics)">进入统计分析</ElButton>
              <ElButton type="primary" plain @click="navigateTo(routeNames.statisticsGallery)">查看样本图库</ElButton>
            </div>

            <div class="dashboard-hero__badges">
              <div
                v-for="badge in focusBadges"
                :key="badge.label"
                class="dashboard-hero__badge"
              >
                <span>{{ badge.label }}</span>
                <strong>{{ badge.value }}</strong>
              </div>
            </div>
          </section>

          <div class="dashboard-metrics">
            <MetricCard
              v-for="item in metricCards"
              :key="item.label"
              :label="item.label"
              :value="item.value"
              :hint="item.hint"
              :accent="item.accent"
            />
          </div>
        </div>

        <div
          class="dashboard-workspace-page"
          :class="{ 'dashboard-workspace-page--active': activeWorkspacePage === 'risk' }"
          data-workspace-page="risk"
        >
          <div class="dashboard-main-grid">
            <section class="app-panel dashboard-panel dashboard-panel--trend">
              <div class="dashboard-panel__header">
                <div>
                  <strong>近期趋势</strong>
                  <p class="muted-text">用总量和构成条判断最近几天是“量在升”还是“风险在聚集”。</p>
                </div>
                <ElTag effect="dark" round type="info">
                  {{ latestTrend ? `最近活跃 ${latestTrend.date}` : "暂无趋势点" }}
                </ElTag>
              </div>

              <div v-if="visibleTrendRows.length > 0" class="dashboard-trend-list">
                <article
                  v-for="item in visibleTrendRows"
                  :key="item.date"
                  class="dashboard-trend-row"
                >
                  <div class="dashboard-trend-row__meta">
                    <strong>{{ item.date }}</strong>
                    <span>总量 {{ item.totalCount }} / 不良 {{ item.badCount }} / 待确认 {{ item.uncertainCount }}</span>
                  </div>
                  <div class="dashboard-trend-row__total-track">
                    <div class="dashboard-trend-row__total-fill" :style="{ width: item.totalWidth }" />
                  </div>
                  <div class="dashboard-trend-row__composition">
                    <div class="dashboard-trend-row__composition-fill is-good" :style="{ width: item.goodWidth }" />
                    <div class="dashboard-trend-row__composition-fill is-bad" :style="{ width: item.badWidth }" />
                    <div class="dashboard-trend-row__composition-fill is-uncertain" :style="{ width: item.uncertainWidth }" />
                  </div>
                </article>

                <div v-if="hiddenTrendRowCount > 0" class="dashboard-trend__footnote">
                  <span class="muted-text">
                    首页仅展示最近 {{ visibleTrendRows.length }} 天，另外 {{ hiddenTrendRowCount }} 天趋势已收起。
                  </span>
                  <ElButton text type="primary" @click="navigateTo(routeNames.statistics)">
                    去统计分析查看完整趋势
                  </ElButton>
                </div>
              </div>
              <ElEmpty v-else description="当前窗口暂无趋势数据" />
            </section>

            <section class="app-panel dashboard-panel dashboard-panel--focus">
              <div class="dashboard-panel__header">
                <div>
                  <strong>风险聚焦</strong>
                  <p class="muted-text">把首页最关键的缺陷、结果结构和审核状态放在一起快速判断。</p>
                </div>
              </div>

              <div class="dashboard-focus__grid">
                <div class="dashboard-focus__block">
                  <div class="dashboard-focus__block-header">
                    <strong>缺陷 Top</strong>
                    <span class="muted-text">{{ defectRows.length }} 项</span>
                  </div>

                  <div v-if="defectRows.length > 0" class="dashboard-defect-list">
                    <article
                      v-for="item in defectRows"
                      :key="item.defectType"
                      class="dashboard-defect-item"
                    >
                      <div class="dashboard-defect-item__meta">
                        <strong>{{ item.defectType }}</strong>
                        <span>{{ item.count }}</span>
                      </div>
                      <div class="dashboard-defect-item__track">
                        <div class="dashboard-defect-item__fill" :style="{ width: item.width }" />
                      </div>
                    </article>
                  </div>
                  <ElEmpty v-else description="暂无缺陷分布数据" />
                </div>

                <div class="dashboard-focus__block">
                  <div class="dashboard-focus__block-header">
                    <strong>结果结构</strong>
                    <span class="muted-text">首页快照</span>
                  </div>

                  <div class="dashboard-result-grid">
                    <article
                      v-for="item in resultCards"
                      :key="item.label"
                      class="dashboard-result-card"
                      :data-accent="item.accent"
                    >
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                      <small>{{ item.ratio }}</small>
                    </article>
                  </div>
                </div>
              </div>

              <div class="dashboard-focus__block dashboard-focus__block--review">
                <div class="dashboard-focus__block-header">
                  <strong>审核状态</strong>
                  <span class="muted-text">当前闭环节奏</span>
                </div>
                <div class="dashboard-review-grid">
                  <article
                    v-for="item in reviewCards"
                    :key="item.label"
                    class="dashboard-review-card"
                    :data-accent="item.accent"
                  >
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </article>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div
          class="dashboard-workspace-page"
          :class="{ 'dashboard-workspace-page--active': activeWorkspacePage === 'actions' }"
          data-workspace-page="actions"
        >
          <div class="dashboard-secondary-grid">
            <section class="app-panel dashboard-panel">
              <div class="dashboard-panel__header">
                <div>
                  <strong>风险排行</strong>
                  <p class="muted-text">优先判断异常更集中在零件侧，还是集中在特定设备链路。</p>
                </div>
                <ElButton text @click="navigateTo(routeNames.statistics)">查看更多</ElButton>
              </div>

              <div class="dashboard-ranking-grid">
                <div class="dashboard-ranking-block">
                  <div class="dashboard-ranking-block__title">零件 Top</div>
                  <article
                    v-for="item in topPartRows"
                    :key="item.partId"
                    class="dashboard-ranking-item"
                  >
                    <div class="dashboard-ranking-item__meta">
                      <strong>{{ item.partName }}</strong>
                      <span>{{ item.partCode }}</span>
                    </div>
                    <div class="dashboard-ranking-item__summary">
                      风险 {{ item.riskCount }} / 总量 {{ item.totalCount }} / 良率 {{ formatPercent(item.passRate) }}
                    </div>
                    <div class="dashboard-ranking-item__track">
                      <div class="dashboard-ranking-item__fill" :style="{ width: item.width }" />
                    </div>
                  </article>
                </div>

                <div class="dashboard-ranking-block">
                  <div class="dashboard-ranking-block__title">设备 Top</div>
                  <article
                    v-for="item in topDeviceRows"
                    :key="item.deviceId"
                    class="dashboard-ranking-item"
                  >
                    <div class="dashboard-ranking-item__meta">
                      <strong>{{ item.deviceName }}</strong>
                      <span>{{ item.deviceCode }}</span>
                    </div>
                    <div class="dashboard-ranking-item__summary">
                      风险 {{ item.riskCount }} / 总量 {{ item.totalCount }} / 良率 {{ formatPercent(item.passRate) }}
                    </div>
                    <div class="dashboard-ranking-item__track">
                      <div class="dashboard-ranking-item__fill is-device" :style="{ width: item.width }" />
                    </div>
                  </article>
                </div>
              </div>
            </section>

            <section class="app-panel dashboard-panel dashboard-panel--gallery">
              <div class="dashboard-panel__header">
                <div>
                  <strong>样本图库概况</strong>
                  <p class="muted-text">首页先看图片覆盖范围，具体图片再进入样本图库或检测记录。</p>
                </div>
              </div>

              <div class="dashboard-gallery__stats">
                <div class="dashboard-gallery__stat">
                  <span>图片总数</span>
                  <strong>{{ sampleGallery?.totalImageCount ?? 0 }}</strong>
                </div>
                <div class="dashboard-gallery__stat">
                  <span>分类数量</span>
                  <strong>{{ sampleGallery?.totalPartCount ?? 0 }}</strong>
                </div>
                <div class="dashboard-gallery__stat">
                  <span>记录数量</span>
                  <strong>{{ sampleGallery?.totalRecordCount ?? 0 }}</strong>
                </div>
                <div class="dashboard-gallery__stat">
                  <span>最近上传</span>
                  <strong>{{ latestUploadText }}</strong>
                </div>
              </div>

              <div class="dashboard-gallery__actions">
                <ElButton plain @click="navigateTo(routeNames.statisticsGallery)">进入样本图库</ElButton>
                <ElButton type="primary" plain @click="navigateTo(routeNames.records)">查看检测记录</ElButton>
              </div>
            </section>
          </div>

          <section class="app-panel dashboard-panel dashboard-panel--findings">
            <div class="dashboard-panel__header">
              <div>
                <strong>关键发现与下一步</strong>
                <p class="muted-text">把当前窗口值得优先处理的问题直接列出来，避免每次都重新阅读全部图表。</p>
              </div>
            </div>

            <div v-if="keyFindings.length > 0" class="dashboard-findings-list">
              <article
                v-for="(item, index) in keyFindings"
                :key="`${index}-${item}`"
                class="dashboard-finding-item"
              >
                <span class="dashboard-finding-item__index">{{ index + 1 }}</span>
                <p>{{ item }}</p>
              </article>
            </div>
            <ElEmpty v-else description="当前窗口暂无关键发现" />
          </section>
        </div>
      </div>
    </template>

    <section v-else-if="loading" class="app-panel dashboard-panel dashboard-panel--empty">
      <ElSkeleton animated :rows="8" />
    </section>

    <section v-else class="app-panel dashboard-panel dashboard-panel--empty">
      <ElEmpty description="当前还没有可展示的仪表盘数据" />
    </section>
  </div>
</template>

<style scoped>
.dashboard-page {
  --dashboard-workspace-stage-height: clamp(620px, calc(100vh - 320px), 900px);
  gap: 22px;
}

.dashboard-pager {
  display: grid;
  gap: 16px;
  padding: 22px;
}

.dashboard-pager__header,
.dashboard-pager__footer,
.dashboard-pager__actions {
  display: flex;
  gap: 14px;
}

.dashboard-pager__header,
.dashboard-pager__footer {
  align-items: flex-start;
  justify-content: space-between;
}

.dashboard-pager__header p,
.dashboard-pager__footer p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.dashboard-pager__grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dashboard-pager__item {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.025);
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.dashboard-pager__item:hover {
  transform: translateY(-1px);
  border-color: rgba(127, 228, 208, 0.28);
}

.dashboard-pager__item--active {
  border-color: rgba(127, 228, 208, 0.46);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 38%),
    rgba(255, 255, 255, 0.04);
}

.dashboard-pager__item-index {
  color: rgba(127, 228, 208, 0.86);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.dashboard-pager__item strong {
  font-size: 15px;
  line-height: 1.4;
}

.dashboard-pager__item span {
  color: var(--app-text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.dashboard-pager__actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.dashboard-workspace-stage {
  display: grid;
  gap: 20px;
  min-height: var(--dashboard-workspace-stage-height);
}

.dashboard-workspace-page {
  display: none;
  gap: 20px;
  align-content: start;
  min-height: var(--dashboard-workspace-stage-height);
  max-height: var(--dashboard-workspace-stage-height);
  overflow-y: auto;
  padding-right: 6px;
}

.dashboard-workspace-page--active {
  display: grid;
}

.dashboard-hero {
  display: grid;
  gap: 18px;
  padding: 24px;
}

.dashboard-hero__copy h2 {
  margin: 8px 0 10px;
  font-size: 28px;
}

.dashboard-hero__copy p {
  margin: 0;
}

.dashboard-hero__eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.dashboard-hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.dashboard-hero__badges {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.dashboard-hero__badge {
  display: grid;
  gap: 8px;
  min-height: 92px;
  padding: 16px 18px;
  border: 1px solid rgba(149, 184, 223, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
}

.dashboard-hero__badge span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.dashboard-hero__badge strong {
  font-size: 18px;
  line-height: 1.5;
}

.dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.dashboard-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.95fr);
  gap: 20px;
  align-items: start;
}

.dashboard-secondary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(340px, 0.9fr);
  gap: 20px;
  align-items: start;
}

.dashboard-panel {
  display: grid;
  gap: 18px;
  padding: 24px;
  align-content: start;
}

.dashboard-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-panel__header p {
  margin: 6px 0 0;
}

.dashboard-trend-list {
  display: grid;
  gap: 14px;
}

.dashboard-trend__footnote {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 2px;
}

.dashboard-trend-row {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
}

.dashboard-trend-row__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.dashboard-trend-row__meta span {
  color: var(--app-text-secondary);
}

.dashboard-trend-row__total-track,
.dashboard-trend-row__composition {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.dashboard-trend-row__total-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(47, 182, 162, 0.9), rgba(106, 167, 255, 0.92));
}

.dashboard-trend-row__composition {
  display: flex;
}

.dashboard-trend-row__composition-fill {
  height: 100%;
}

.dashboard-trend-row__composition-fill.is-good {
  background: rgba(76, 214, 154, 0.94);
}

.dashboard-trend-row__composition-fill.is-bad {
  background: rgba(240, 101, 101, 0.94);
}

.dashboard-trend-row__composition-fill.is-uncertain {
  background: rgba(242, 184, 75, 0.94);
}

.dashboard-focus__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(220px, 0.95fr);
  gap: 18px;
}

.dashboard-focus__block {
  display: grid;
  gap: 14px;
}

.dashboard-focus__block--review {
  padding-top: 4px;
  border-top: 1px solid rgba(149, 184, 223, 0.12);
}

.dashboard-focus__block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-defect-list {
  display: grid;
  gap: 12px;
}

.dashboard-defect-item {
  display: grid;
  gap: 8px;
}

.dashboard-defect-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
}

.dashboard-defect-item__meta span {
  color: var(--app-primary);
  font-weight: 700;
}

.dashboard-defect-item__track,
.dashboard-ranking-item__track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.dashboard-defect-item__fill,
.dashboard-ranking-item__fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(47, 182, 162, 0.95), rgba(127, 228, 208, 0.86));
}

.dashboard-result-grid,
.dashboard-review-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-result-card,
.dashboard-review-card {
  display: grid;
  gap: 8px;
  min-height: 94px;
  padding: 14px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.025);
}

.dashboard-result-card span,
.dashboard-review-card span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.dashboard-result-card strong,
.dashboard-review-card strong {
  font-size: 24px;
}

.dashboard-result-card small {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.dashboard-result-card[data-accent="success"],
.dashboard-review-card[data-accent="success"] {
  border-color: rgba(76, 214, 154, 0.28);
}

.dashboard-result-card[data-accent="danger"] {
  border-color: rgba(240, 101, 101, 0.28);
}

.dashboard-result-card[data-accent="warning"],
.dashboard-review-card[data-accent="warning"] {
  border-color: rgba(242, 184, 75, 0.28);
}

.dashboard-review-card[data-accent="info"] {
  border-color: rgba(106, 167, 255, 0.28);
}

.dashboard-ranking-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.dashboard-ranking-block {
  display: grid;
  gap: 14px;
}

.dashboard-ranking-block__title {
  color: var(--app-text-secondary);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dashboard-ranking-item {
  display: grid;
  gap: 8px;
}

.dashboard-ranking-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-ranking-item__meta span,
.dashboard-ranking-item__summary {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.dashboard-ranking-item__fill {
  background: linear-gradient(90deg, rgba(240, 101, 101, 0.95), rgba(242, 184, 75, 0.88));
}

.dashboard-ranking-item__fill.is-device {
  background: linear-gradient(90deg, rgba(106, 167, 255, 0.95), rgba(47, 182, 162, 0.88));
}

.dashboard-gallery__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-gallery__stat {
  display: grid;
  gap: 8px;
  min-height: 102px;
  padding: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
}

.dashboard-gallery__stat span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.dashboard-gallery__stat strong {
  font-size: 22px;
  line-height: 1.4;
}

.dashboard-gallery__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.dashboard-findings-list {
  display: grid;
  gap: 14px;
}

.dashboard-finding-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  padding: 16px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.025);
}

.dashboard-finding-item p {
  margin: 0;
  line-height: 1.8;
}

.dashboard-finding-item__index {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  color: #081523;
  font-size: 13px;
  font-weight: 700;
  background: linear-gradient(135deg, rgba(127, 228, 208, 0.98), rgba(106, 167, 255, 0.92));
}

.dashboard-panel--empty {
  padding: 24px;
}

@media (max-width: 1280px) {
  .dashboard-pager__grid,
  .dashboard-main-grid,
  .dashboard-secondary-grid,
  .dashboard-hero__badges,
  .dashboard-metrics,
  .dashboard-ranking-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-focus__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .dashboard-page {
    --dashboard-workspace-stage-height: auto;
  }

  .dashboard-pager__header,
  .dashboard-pager__footer,
  .dashboard-pager__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .dashboard-main-grid,
  .dashboard-secondary-grid,
  .dashboard-hero__badges,
  .dashboard-metrics,
  .dashboard-pager__grid,
  .dashboard-result-grid,
  .dashboard-review-grid,
  .dashboard-gallery__stats,
  .dashboard-ranking-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .dashboard-trend-row__meta,
  .dashboard-panel__header,
  .dashboard-focus__block-header,
  .dashboard-ranking-item__meta,
  .dashboard-trend__footnote {
    flex-direction: column;
    align-items: flex-start;
  }

  .dashboard-workspace-stage,
  .dashboard-workspace-page {
    min-height: auto;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }
}

@media print {
  .dashboard-pager {
    display: none !important;
  }

  .dashboard-main-grid,
  .dashboard-secondary-grid,
  .dashboard-hero__badges,
  .dashboard-metrics,
  .dashboard-focus__grid,
  .dashboard-result-grid,
  .dashboard-review-grid,
  .dashboard-gallery__stats,
  .dashboard-ranking-grid {
    grid-template-columns: 1fr !important;
  }

  .dashboard-hero__actions {
    display: none !important;
  }

  .dashboard-trend-row__meta,
  .dashboard-panel__header,
  .dashboard-focus__block-header,
  .dashboard-ranking-item__meta,
  .dashboard-trend__footnote {
    flex-direction: column;
    align-items: flex-start;
  }

  .dashboard-workspace-page {
    display: grid !important;
    min-height: auto;
    max-height: none;
    overflow: visible;
    padding-right: 0;
    break-before: page;
    page-break-before: always;
  }

  .dashboard-workspace-page:first-child {
    break-before: auto;
    page-break-before: auto;
  }
}
</style>
