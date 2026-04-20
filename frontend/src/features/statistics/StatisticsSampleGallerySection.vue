<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import MetricCard from "@/components/common/MetricCard.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import { routeNames } from "@/router/routes";
import type { FileKind } from "@/types/api";
import type { StatisticsSampleGallery, StatisticsSampleImageItem } from "@/types/models";
import { formatDateTime } from "@/utils/format";

import {
  SAMPLE_GALLERY_ALL_ENTRY_KEY,
  buildSampleGalleryCategoryEntryKey,
  groupSampleGalleryByCategory,
} from "./sampleGallery";

const props = withDefaults(
  defineProps<{
    gallery: StatisticsSampleGallery | null;
    initialCategoryLabel?: string | null;
  }>(),
  {
    initialCategoryLabel: null,
  },
);

const router = useRouter();

/**
 * 当前选中的图库入口。
 * 默认先展示“全部图片”，满足用户进入统计页后先看整体样本分布的诉求。
 */
const activeEntryKey = ref(SAMPLE_GALLERY_ALL_ENTRY_KEY);

/**
 * 把图库按零件分类整理成入口列表。
 * 这样页面既能显示“全部图片”总入口，也能显示各分类单独入口。
 */
const categoryEntries = computed(() => groupSampleGalleryByCategory(props.gallery));

/**
 * 当前是否存在任何可展示的样本图记录。
 */
const hasGallery = computed(() => (props.gallery?.totalRecordCount ?? 0) > 0);

/**
 * 根据当前入口筛选要展示的分类内容。
 * “全部图片”入口会把所有分类都展示出来，其他入口只保留当前分类。
 */
const displayedCategoryEntries = computed(() => {
  if (activeEntryKey.value === SAMPLE_GALLERY_ALL_ENTRY_KEY) {
    return categoryEntries.value;
  }

  return categoryEntries.value.filter((item) => item.key === activeEntryKey.value);
});

/**
 * 当前入口下方的说明文字。
 * 这能帮助用户明确自己看到的是全量图片，还是某个分类的局部图片。
 */
const activeEntryHint = computed(() => {
  if (!hasGallery.value || !props.gallery) {
    return "当前筛选窗口内还没有可用于统计展示的样本图片。";
  }

  if (activeEntryKey.value === SAMPLE_GALLERY_ALL_ENTRY_KEY) {
    return `全部图片入口会展示当前统计窗口内的 ${props.gallery.totalRecordCount} 条样本记录，并按零件分类自动分区。`;
  }

  const activeEntry = categoryEntries.value.find((item) => item.key === activeEntryKey.value);
  if (!activeEntry) {
    return "当前入口对应的分类已不存在，已自动回退到全部图片入口。";
  }

  return `当前只展示“${activeEntry.label}”分类下的 ${activeEntry.recordCount} 条检测记录，方便直接进入人工复检。`;
});

/**
 * 当统计窗口变化导致分类入口改变时，自动兜底回到有效入口。
 * 这样切换筛选条件后不会出现“入口仍然选中旧分类，但页面内容为空”的错位状态。
 */
watch(
  () => categoryEntries.value.map((item) => item.key),
  (entryKeys) => {
    if (
      activeEntryKey.value !== SAMPLE_GALLERY_ALL_ENTRY_KEY
      && !entryKeys.includes(activeEntryKey.value)
    ) {
      activeEntryKey.value = SAMPLE_GALLERY_ALL_ENTRY_KEY;
    }
  },
  { immediate: true },
);

/**
 * 独立图库页可通过路由查询参数指定默认分类入口。
 * 如果当前分类不存在，则自动回退到“全部图片”。
 */
watch(
  () => [props.initialCategoryLabel, categoryEntries.value.map((item) => item.label).join("|")],
  () => {
    if (!props.initialCategoryLabel) {
      activeEntryKey.value = SAMPLE_GALLERY_ALL_ENTRY_KEY;
      return;
    }

    const targetKey = buildSampleGalleryCategoryEntryKey(props.initialCategoryLabel);
    activeEntryKey.value = categoryEntries.value.some((item) => item.key === targetKey)
      ? targetKey
      : SAMPLE_GALLERY_ALL_ENTRY_KEY;
  },
  { immediate: true },
);

/**
 * 跳转到单条检测记录详情页。
 * 统计页只负责筛选和总览，真正的人工复检仍然在详情工作区里完成。
 */
function openRecordDetail(recordId: number): void {
  void router.push({
    name: routeNames.recordDetail,
    params: {
      id: recordId,
    },
  });
}

/**
 * 把图片类型转换成短标签，帮助用户理解当前卡片展示的是哪一类主图。
 */
function getFileKindLabel(fileKind: FileKind | null): string {
  if (fileKind === "annotated") {
    return "标注图";
  }
  if (fileKind === "source") {
    return "源图";
  }
  if (fileKind === "thumbnail") {
    return "缩略图";
  }
  return "待补图";
}

/**
 * 统一生成人类可读的图片数量文案。
 */
function formatImageCountLabel(imageCount: number): string {
  return `共 ${imageCount} 张图`;
}

/**
 * 为预览图片生成可读的替代文本。
 */
function buildPreviewAlt(item: StatisticsSampleImageItem): string {
  return `${item.partName} ${item.recordNo} 预览图`;
}

/**
 * 组合当前记录最值得用户先读到的缺陷摘要。
 * 优先展示缺陷类型，没有时再退回缺陷说明，再没有就给出明确占位。
 */
function buildDefectSummary(item: StatisticsSampleImageItem): string {
  if (item.defectType && item.defectDesc) {
    return `${item.defectType}：${item.defectDesc}`;
  }
  if (item.defectType) {
    return item.defectType;
  }
  if (item.defectDesc) {
    return item.defectDesc;
  }
  return "当前记录未填写缺陷说明，可进入复检界面查看完整上下文。";
}
</script>

<template>
  <section class="app-panel stats-gallery">
    <div class="stats-gallery__header">
      <div>
        <strong>样本图库与复检入口</strong>
        <p class="muted-text">
          这里集中展示当前窗口内的样本图片，并按零件分类提供入口。你可以先从“全部图片”总入口看全局，再进入某个分类，最后一键跳到对应记录的人工复检界面。
        </p>
      </div>
      <ElTag v-if="gallery" effect="dark" round type="info">
        最近上传 {{ formatDateTime(gallery.latestUploadedAt) }}
      </ElTag>
    </div>

    <div class="stats-gallery__metrics">
      <MetricCard
        label="图片总数"
        :value="String(gallery?.totalImageCount ?? 0)"
        hint="当前筛选窗口内已登记的样本图片总量"
      />
      <MetricCard
        label="样本记录"
        :value="String(gallery?.totalRecordCount ?? 0)"
        hint="这些记录都可以继续进入复检详情页"
        accent="info"
      />
      <MetricCard
        label="零件类别"
        :value="String(categoryEntries.length)"
        hint="统计页已自动生成对应的分类入口"
        accent="success"
      />
      <MetricCard
        label="零件分组"
        :value="String(gallery?.totalPartCount ?? 0)"
        hint="按零件型号拆分后的分组数量"
        accent="warning"
      />
    </div>

    <ElEmpty
      v-if="!hasGallery"
      description="当前筛选窗口内还没有可展示的样本图片。"
    />

    <template v-else>
      <div class="stats-gallery__entry-bar">
        <ElButton
          round
          :type="activeEntryKey === SAMPLE_GALLERY_ALL_ENTRY_KEY ? 'primary' : 'default'"
          @click="activeEntryKey = SAMPLE_GALLERY_ALL_ENTRY_KEY"
        >
          全部图片
        </ElButton>

        <ElButton
          v-for="entry in categoryEntries"
          :key="entry.key"
          round
          :type="activeEntryKey === entry.key ? 'primary' : 'default'"
          plain
          @click="activeEntryKey = entry.key"
        >
          {{ entry.label }} · {{ entry.recordCount }}
        </ElButton>
      </div>

      <p class="stats-gallery__entry-hint muted-text">
        {{ activeEntryHint }}
      </p>

      <div class="stats-gallery__category-list">
        <section
          v-for="entry in displayedCategoryEntries"
          :key="entry.key"
          class="stats-gallery__category-section"
        >
          <div class="stats-gallery__category-header">
            <div>
              <strong>{{ entry.label }}</strong>
              <p class="muted-text">
                共 {{ entry.groupCount }} 个零件分组，{{ entry.recordCount }} 条检测记录，{{ entry.imageCount }} 张图片
              </p>
            </div>
            <ElTag effect="dark" round type="info">
              最近上传 {{ formatDateTime(entry.latestUploadedAt) }}
            </ElTag>
          </div>

          <div class="stats-gallery__group-list">
            <article
              v-for="group in entry.groups"
              :key="group.partId"
              class="stats-gallery__group-card"
            >
              <div class="stats-gallery__group-header">
                <div>
                  <strong>{{ group.partName }}</strong>
                  <p class="muted-text">
                    {{ group.partCode }} · {{ group.recordCount }} 条记录 · {{ group.imageCount }} 张图片
                  </p>
                </div>
                <ElTag effect="dark" round>
                  最近上传 {{ formatDateTime(group.latestUploadedAt) }}
                </ElTag>
              </div>

              <div class="stats-gallery__item-grid">
                <article
                  v-for="item in group.items"
                  :key="item.recordId"
                  class="stats-gallery__item-card"
                >
                  <div class="stats-gallery__preview">
                    <img
                      v-if="item.previewUrl"
                      :src="item.previewUrl"
                      :alt="buildPreviewAlt(item)"
                      class="stats-gallery__preview-image"
                      loading="lazy"
                    >
                    <div v-else class="stats-gallery__preview-fallback">
                      <strong>{{ getFileKindLabel(item.imageFileKind) }}</strong>
                      <span>{{ formatImageCountLabel(item.imageCount) }}</span>
                    </div>

                    <span class="stats-gallery__preview-badge">
                      {{ getFileKindLabel(item.imageFileKind) }}
                    </span>
                  </div>

                  <div class="stats-gallery__item-body">
                    <div class="stats-gallery__item-title">
                      <strong>{{ item.recordNo }}</strong>
                      <ElTag type="info" effect="dark" round>
                        {{ formatImageCountLabel(item.imageCount) }}
                      </ElTag>
                    </div>

                    <div class="stats-gallery__item-tags">
                      <StatusTag :value="item.effectiveResult" />
                      <StatusTag :value="item.reviewStatus" />
                    </div>

                    <div class="stats-gallery__item-meta">
                      <span>设备：{{ item.deviceName }} / {{ item.deviceCode }}</span>
                      <span>拍摄：{{ formatDateTime(item.capturedAt) }}</span>
                      <span>上传：{{ formatDateTime(item.uploadedAt) }}</span>
                    </div>

                    <p class="stats-gallery__item-defect">
                      {{ buildDefectSummary(item) }}
                    </p>

                    <div class="stats-gallery__item-actions">
                      <ElButton type="primary" @click="openRecordDetail(item.recordId)">
                        进入复检界面
                      </ElButton>
                    </div>
                  </div>
                </article>
              </div>
            </article>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.stats-gallery,
.stats-gallery__metrics,
.stats-gallery__category-list,
.stats-gallery__group-list,
.stats-gallery__item-grid,
.stats-gallery__item-body {
  display: grid;
  gap: 18px;
}

.stats-gallery {
  padding: 24px;
}

.stats-gallery__header,
.stats-gallery__category-header,
.stats-gallery__group-header,
.stats-gallery__item-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.stats-gallery__header p,
.stats-gallery__category-header p,
.stats-gallery__group-header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-gallery__metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stats-gallery__entry-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.stats-gallery__entry-hint {
  margin: 0;
  line-height: 1.7;
}

.stats-gallery__category-section,
.stats-gallery__group-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid rgba(127, 228, 208, 0.12);
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(20, 40, 58, 0.82), rgba(11, 25, 39, 0.96));
}

.stats-gallery__item-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.stats-gallery__item-card {
  display: grid;
  /* 宽屏下把图片和说明拆成左右两栏，避免单张图片横向铺满整张卡片。 */
  grid-template-columns: minmax(260px, clamp(280px, 32vw, 420px)) minmax(0, 1fr);
  align-items: start;
  gap: 14px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(8, 20, 33, 0.88);
  border: 1px solid rgba(106, 167, 255, 0.14);
}

.stats-gallery__preview {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  aspect-ratio: 4 / 3;
  /* 预览区保留稳定舞台，但通过最大高度限制桌面宽屏下的图片体量。 */
  max-height: clamp(220px, 30vw, 340px);
  padding: 14px;
  border-radius: 16px;
  background:
    radial-gradient(circle at top left, rgba(127, 228, 208, 0.2), transparent 45%),
    linear-gradient(160deg, rgba(20, 45, 62, 0.96), rgba(8, 20, 33, 0.98));
}

.stats-gallery__preview-image {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
}

.stats-gallery__preview-fallback {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  gap: 8px;
  color: var(--app-text-secondary);
  text-align: center;
  padding: 18px;
}

.stats-gallery__preview-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(8, 20, 33, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #f8fbff;
  font-size: 12px;
  font-weight: 600;
}

.stats-gallery__item-tags,
.stats-gallery__item-meta,
.stats-gallery__item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.stats-gallery__item-meta {
  color: var(--app-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.stats-gallery__item-defect {
  margin: 0;
  color: var(--app-text-secondary);
  line-height: 1.7;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

@media (max-width: 1280px) {
  .stats-gallery__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-gallery__header,
  .stats-gallery__category-header,
  .stats-gallery__group-header,
  .stats-gallery__item-title {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-gallery__metrics,
  .stats-gallery__item-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .stats-gallery__item-card {
    /* 移动端恢复单列，保证信息区不会被压缩。 */
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
