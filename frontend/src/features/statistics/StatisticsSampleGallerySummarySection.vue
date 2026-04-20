<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";

import MetricCard from "@/components/common/MetricCard.vue";
import { routeNames } from "@/router/routes";
import type { StatisticsFilters, StatisticsSampleGallery } from "@/types/models";
import { formatDateTime } from "@/utils/format";

import {
  buildStatisticsGalleryRouteQuery,
  groupSampleGalleryByCategory,
} from "./sampleGallery";

const props = defineProps<{
  gallery: StatisticsSampleGallery | null;
  filters: StatisticsFilters | null;
}>();

const router = useRouter();

/**
 * 统计页只展示分类入口摘要，不直接铺满所有图片。
 * 这里保留按分类聚合后的入口卡片，真正的图片浏览交给独立图库页。
 */
const categoryEntries = computed(() => groupSampleGalleryByCategory(props.gallery));

/**
 * 统计页摘要区只展示前几类，避免入口本身再次膨胀成一大面图片墙。
 */
const previewEntries = computed(() => categoryEntries.value.slice(0, 6));

/**
 * 当前是否存在可进入图库页的数据。
 */
const hasGallery = computed(() => (props.gallery?.totalRecordCount ?? 0) > 0);

/**
 * 跳到独立图库页。
 * 如果传入分类，则直接定位到该分类入口；否则打开全量总入口。
 */
function openGallery(categoryLabel?: string | null): void {
  if (!props.filters) {
    return;
  }

  void router.push({
    name: routeNames.statisticsGallery,
    query: buildStatisticsGalleryRouteQuery(props.filters, categoryLabel),
  });
}
</script>

<template>
  <section class="app-panel stats-gallery-summary">
    <div class="stats-gallery-summary__header">
      <div>
        <strong>样本图库入口</strong>
        <p class="muted-text">
          统计页这里改成小入口。真正的图片浏览、分类切换和进入复检，统一下沉到独立图库页处理。
        </p>
      </div>

      <div class="stats-gallery-summary__actions">
        <ElTag v-if="gallery" effect="dark" round type="info">
          最近上传 {{ formatDateTime(gallery.latestUploadedAt) }}
        </ElTag>
        <ElButton type="primary" :disabled="!hasGallery" @click="openGallery()">
          打开图库总览
        </ElButton>
      </div>
    </div>

    <div class="stats-gallery-summary__metrics">
      <MetricCard
        label="图片总数"
        :value="String(gallery?.totalImageCount ?? 0)"
        hint="当前统计窗口内已登记的样本图片"
      />
      <MetricCard
        label="样本记录"
        :value="String(gallery?.totalRecordCount ?? 0)"
        hint="这些记录都可以继续进入人工复检"
        accent="info"
      />
      <MetricCard
        label="零件类别"
        :value="String(categoryEntries.length)"
        hint="已自动整理成分类入口"
        accent="success"
      />
      <MetricCard
        label="零件分组"
        :value="String(gallery?.totalPartCount ?? 0)"
        hint="按零件类型拆分后的具体分组"
        accent="warning"
      />
    </div>

    <ElEmpty
      v-if="!hasGallery"
      description="当前筛选窗口内还没有可展示的样本图片。"
    />

    <div v-else class="stats-gallery-summary__entry-grid">
      <article
        v-for="entry in previewEntries"
        :key="entry.key"
        class="stats-gallery-summary__entry-card"
      >
        <div class="stats-gallery-summary__entry-head">
          <div>
            <strong>{{ entry.label }}</strong>
            <p class="muted-text">
              {{ entry.groupCount }} 个零件分组，{{ entry.recordCount }} 条记录，{{ entry.imageCount }} 张图片
            </p>
          </div>
          <ElTag effect="dark" round>
            最近上传 {{ formatDateTime(entry.latestUploadedAt) }}
          </ElTag>
        </div>

        <div class="stats-gallery-summary__entry-actions">
          <ElButton plain @click="openGallery(entry.label)">
            查看该分类
          </ElButton>
        </div>
      </article>

      <article
        v-if="categoryEntries.length > previewEntries.length"
        class="stats-gallery-summary__entry-card stats-gallery-summary__entry-card--more"
      >
        <strong>还有 {{ categoryEntries.length - previewEntries.length }} 个分类入口</strong>
        <p class="muted-text">
          为了保持统计页清晰，这里只展示前 {{ previewEntries.length }} 个分类，其余入口请进入图库总览查看。
        </p>
        <div class="stats-gallery-summary__entry-actions">
          <ElButton type="primary" plain @click="openGallery()">
            查看全部分类
          </ElButton>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.stats-gallery-summary,
.stats-gallery-summary__metrics,
.stats-gallery-summary__entry-grid {
  display: grid;
  gap: 18px;
}

.stats-gallery-summary {
  padding: 24px;
}

.stats-gallery-summary__header,
.stats-gallery-summary__actions,
.stats-gallery-summary__entry-head,
.stats-gallery-summary__entry-actions {
  display: flex;
  gap: 14px;
}

.stats-gallery-summary__header,
.stats-gallery-summary__entry-head {
  align-items: flex-start;
  justify-content: space-between;
}

.stats-gallery-summary__actions,
.stats-gallery-summary__entry-actions {
  align-items: center;
}

.stats-gallery-summary__header p,
.stats-gallery-summary__entry-head p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-gallery-summary__metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stats-gallery-summary__entry-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.stats-gallery-summary__entry-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid rgba(127, 228, 208, 0.12);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.08), transparent 36%),
    rgba(255, 255, 255, 0.02);
}

.stats-gallery-summary__entry-card--more {
  border-style: dashed;
}

@media (max-width: 1280px) {
  .stats-gallery-summary__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-gallery-summary__header,
  .stats-gallery-summary__actions,
  .stats-gallery-summary__entry-head,
  .stats-gallery-summary__entry-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-gallery-summary__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
