<script setup lang="ts">
import { computed, ref, watch } from "vue";

import PageHeader from "@/components/common/PageHeader.vue";
import StatisticsSampleGallerySection from "@/features/statistics/StatisticsSampleGallerySection.vue";
import { fetchStatisticsSampleGallery } from "@/services/api/statistics";
import { mapStatisticsSampleGalleryResponseDto } from "@/services/mappers/commonMappers";
import type { StatisticsSampleGallery } from "@/types/models";
import { formatDateTime } from "@/utils/format";
import { useRoute } from "vue-router";

const route = useRoute();

const loading = ref(false);
const error = ref("");
const gallery = ref<StatisticsSampleGallery | null>(null);

/**
 * 从路由查询参数解析图库页筛选条件。
 * 这里与统计页保持同一套 query 命名，便于从多个入口稳定跳转。
 */
const filters = computed(() => {
  const parseSingleQueryValue = (value: unknown): string | null => {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    return null;
  };
  const parseOptionalNumber = (value: unknown): number | null => {
    const normalizedValue = parseSingleQueryValue(value);
    if (!normalizedValue) {
      return null;
    }

    const parsedNumber = Number(normalizedValue);
    return Number.isFinite(parsedNumber) ? parsedNumber : null;
  };

  const parsedDays = parseOptionalNumber(route.query.days);

  return {
    startDate: parseSingleQueryValue(route.query.start_date),
    endDate: parseSingleQueryValue(route.query.end_date),
    days: parsedDays ?? 14,
    partId: parseOptionalNumber(route.query.part_id),
    deviceId: parseOptionalNumber(route.query.device_id),
    initialCategoryLabel: parseSingleQueryValue(route.query.category),
  };
});

/**
 * 页面顶部展示当前图库作用范围，避免用户不知道自己看到的是哪一批数据。
 */
const scopeDescription = computed(() => {
  return [
    `${filters.value.startDate ?? "未限定"} 至 ${filters.value.endDate ?? "未限定"}`,
    `窗口 ${filters.value.days} 天`,
    filters.value.partId !== null ? `零件类型 ID ${filters.value.partId}` : null,
    filters.value.deviceId !== null ? `设备 ID ${filters.value.deviceId}` : null,
  ]
    .filter(Boolean)
    .join(" | ");
});

/**
 * 拉取独立图库页数据。
 */
async function loadGallery(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    const response = await fetchStatisticsSampleGallery({
      startDate: filters.value.startDate,
      endDate: filters.value.endDate,
      days: filters.value.days,
      partId: filters.value.partId,
      deviceId: filters.value.deviceId,
    });
    gallery.value = mapStatisticsSampleGalleryResponseDto(response);
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "样本图库加载失败";
  } finally {
    loading.value = false;
  }
}

watch(
  () => route.fullPath,
  () => {
    void loadGallery();
  },
  { immediate: true },
);
</script>

<template>
  <div class="page-grid">
    <PageHeader
      eyebrow="Gallery"
      title="样本图库"
      description="这里专门负责按零件分类浏览样本图片，并从分类入口进入对应记录的人工复检详情。统计页不再直接铺满所有图片。"
    />

    <section class="app-panel gallery-page__scope">
      <div>
        <strong>当前窗口</strong>
        <p class="muted-text">{{ scopeDescription }}</p>
      </div>
      <ElTag v-if="gallery" effect="dark" round type="info">
        最近上传 {{ formatDateTime(gallery.latestUploadedAt) }}
      </ElTag>
    </section>

    <ElAlert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      title="样本图库加载失败"
      :description="error"
    />

    <section v-else-if="loading" class="app-panel gallery-page__loading">
      <ElSkeleton animated :rows="10" />
    </section>

    <StatisticsSampleGallerySection
      v-else
      :gallery="gallery"
      :initial-category-label="filters.initialCategoryLabel"
    />
  </div>
</template>

<style scoped>
.gallery-page__scope,
.gallery-page__loading {
  padding: 22px;
}

.gallery-page__scope {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.gallery-page__scope p {
  margin: 8px 0 0;
  line-height: 1.7;
}

@media (max-width: 900px) {
  .gallery-page__scope {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
