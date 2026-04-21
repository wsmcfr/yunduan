<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import MetricCard from "@/components/common/MetricCard.vue";
import StatusTag from "@/components/common/StatusTag.vue";
import { routeNames } from "@/router/routes";
import type { FileKind } from "@/types/api";
import type {
  StatisticsPartImageGroup,
  StatisticsSampleGallery,
  StatisticsSampleImageItem,
} from "@/types/models";
import { formatDateTime } from "@/utils/format";

import {
  SAMPLE_GALLERY_ALL_ENTRY_KEY,
  buildSampleGalleryCategoryEntryKey,
  groupSampleGalleryByCategory,
} from "./sampleGallery";

type RailKind = "group" | "sample";
type RailDirection = "prev" | "next";

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
 * 默认先展示“全部图片”，满足用户进入图库页后先看整体分类分布的诉求。
 */
const activeEntryKey = ref(SAMPLE_GALLERY_ALL_ENTRY_KEY);

/**
 * 每个分类入口下当前选中的零件类型。
 * 图库现在先选分类，再在分类内部左右切换具体类型。
 */
const activeGroupIdByEntryKey = ref<Record<string, number>>({});

/**
 * 把图库按零件分类整理成入口列表。
 */
const categoryEntries = computed(() => groupSampleGalleryByCategory(props.gallery));

/**
 * 当前是否存在任何可展示的样本图记录。
 */
const hasGallery = computed(() => (props.gallery?.totalRecordCount ?? 0) > 0);

/**
 * 根据当前入口筛选要展示的分类内容。
 */
const displayedCategoryEntries = computed(() => {
  if (activeEntryKey.value === SAMPLE_GALLERY_ALL_ENTRY_KEY) {
    return categoryEntries.value;
  }

  return categoryEntries.value.filter((item) => item.key === activeEntryKey.value);
});

/**
 * 当前入口下方的说明文字。
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

  return `当前只展示“${activeEntry.label}”分类，并可在分类内部左右滑动切换不同零件类型和样本。`;
});

/**
 * 当统计窗口变化导致分类入口改变时，自动兜底回到有效入口。
 */
watch(
  () => categoryEntries.value.map((item) => item.key).join("|"),
  () => {
    if (
      activeEntryKey.value !== SAMPLE_GALLERY_ALL_ENTRY_KEY
      && !categoryEntries.value.some((item) => item.key === activeEntryKey.value)
    ) {
      activeEntryKey.value = SAMPLE_GALLERY_ALL_ENTRY_KEY;
    }
  },
  { immediate: true },
);

/**
 * 独立图库页可通过路由查询参数指定默认分类入口。
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
 * 为每个分类入口补齐默认选中的零件类型。
 * 如果之前选中的类型已不存在，则自动回退到该分类下的第一项。
 */
watch(
  () => displayedCategoryEntries.value,
  (entries) => {
    const nextState: Record<string, number> = {};

    for (const entry of entries) {
      const currentGroupId = activeGroupIdByEntryKey.value[entry.key];
      const hasCurrentGroup = entry.groups.some((group) => group.partId === currentGroupId);
      nextState[entry.key] = hasCurrentGroup ? currentGroupId : (entry.groups[0]?.partId ?? 0);
    }

    activeGroupIdByEntryKey.value = nextState;
  },
  { immediate: true },
);

/**
 * 根据分类入口和零件类型生成 DOM 级别的稳定 rail id。
 * 这样横向滚动控制不需要维护复杂的 ref Map。
 */
function buildRailDomId(kind: RailKind, key: string): string {
  return `${kind}-rail-${encodeURIComponent(key)}`;
}

/**
 * 为“样本横向 rail”生成稳定 key。
 */
function buildSampleRailKey(entryKey: string, partId: number): string {
  return `${entryKey}:${partId}`;
}

/**
 * 返回指定分类下当前激活的零件类型分组。
 */
function resolveActiveGroup(entry: { key: string; groups: StatisticsPartImageGroup[] }): StatisticsPartImageGroup | null {
  const activeGroupId = activeGroupIdByEntryKey.value[entry.key];
  return entry.groups.find((group) => group.partId === activeGroupId) ?? entry.groups[0] ?? null;
}

/**
 * 切换分类内当前选中的零件类型。
 */
function selectGroup(entryKey: string, partId: number): void {
  activeGroupIdByEntryKey.value = {
    ...activeGroupIdByEntryKey.value,
    [entryKey]: partId,
  };
}

/**
 * 横向滚动分类内的零件类型 rail 或样本 rail。
 */
function scrollRail(kind: RailKind, key: string, direction: RailDirection): void {
  const railElement = document.getElementById(buildRailDomId(kind, key));
  if (!(railElement instanceof HTMLElement)) {
    return;
  }

  const offset = Math.max(railElement.clientWidth * 0.82, 240);
  railElement.scrollBy({
    left: direction === "next" ? offset : -offset,
    behavior: "smooth",
  });
}

/**
 * 跳转到单条检测记录详情页。
 * 图库页只负责分类浏览和样本预览，真正的人工复检仍然在详情工作区里完成。
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
 * 把图片类型转换成短标签。
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
          这里集中展示当前窗口内的样本图片，并按零件分类提供入口。你可以先从分类入口切换，再在分类内部左右滑动查看不同类型和样本。
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

          <div class="stats-gallery__selector-header">
            <div>
              <strong>分类内零件类型</strong>
              <p class="muted-text">左右滑动切换同一分类下的不同类型，避免图片纵向堆满页面。</p>
            </div>
            <div class="stats-gallery__selector-actions">
              <ElButton text @click="scrollRail('group', entry.key, 'prev')">向左</ElButton>
              <ElButton text @click="scrollRail('group', entry.key, 'next')">向右</ElButton>
            </div>
          </div>

          <div
            :id="buildRailDomId('group', entry.key)"
            class="stats-gallery__group-rail"
          >
            <button
              v-for="group in entry.groups"
              :key="group.partId"
              type="button"
              class="stats-gallery__group-chip"
              :class="{
                'stats-gallery__group-chip--active': resolveActiveGroup(entry)?.partId === group.partId,
              }"
              @click="selectGroup(entry.key, group.partId)"
            >
              <strong>{{ group.partName }}</strong>
              <span>{{ group.partCode }}</span>
              <span>{{ group.recordCount }} 条记录 · {{ group.imageCount }} 张图片</span>
            </button>
          </div>

          <section
            v-if="resolveActiveGroup(entry)"
            class="stats-gallery__group-focus"
          >
            <div class="stats-gallery__group-focus-header">
              <div>
                <strong>{{ resolveActiveGroup(entry)?.partName }}</strong>
                <p class="muted-text">
                  {{ resolveActiveGroup(entry)?.partCode }}
                  · {{ resolveActiveGroup(entry)?.recordCount }} 条记录
                  · {{ resolveActiveGroup(entry)?.imageCount }} 张图片
                </p>
              </div>
              <div class="stats-gallery__selector-actions">
                <ElButton
                  text
                  @click="scrollRail('sample', buildSampleRailKey(entry.key, resolveActiveGroup(entry)?.partId ?? 0), 'prev')"
                >
                  向左
                </ElButton>
                <ElButton
                  text
                  @click="scrollRail('sample', buildSampleRailKey(entry.key, resolveActiveGroup(entry)?.partId ?? 0), 'next')"
                >
                  向右
                </ElButton>
              </div>
            </div>

            <div
              :id="buildRailDomId('sample', buildSampleRailKey(entry.key, resolveActiveGroup(entry)?.partId ?? 0))"
              class="stats-gallery__sample-rail"
            >
              <article
                v-for="item in resolveActiveGroup(entry)?.items ?? []"
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
          </section>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.stats-gallery,
.stats-gallery__metrics,
.stats-gallery__category-list,
.stats-gallery__group-focus,
.stats-gallery__item-body {
  display: grid;
  gap: 18px;
}

.stats-gallery {
  padding: 24px;
}

.stats-gallery__header,
.stats-gallery__category-header,
.stats-gallery__selector-header,
.stats-gallery__group-focus-header,
.stats-gallery__item-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.stats-gallery__header p,
.stats-gallery__category-header p,
.stats-gallery__selector-header p,
.stats-gallery__group-focus-header p {
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

.stats-gallery__category-section {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid rgba(127, 228, 208, 0.12);
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(20, 40, 58, 0.82), rgba(11, 25, 39, 0.96));
}

.stats-gallery__selector-actions,
.stats-gallery__item-tags,
.stats-gallery__item-meta,
.stats-gallery__item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.stats-gallery__group-rail,
.stats-gallery__sample-rail {
  display: grid;
  grid-auto-flow: column;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 6px;
  scroll-snap-type: x proximity;
}

.stats-gallery__group-rail {
  grid-auto-columns: minmax(220px, 260px);
}

.stats-gallery__sample-rail {
  grid-auto-columns: minmax(280px, 340px);
}

.stats-gallery__group-chip {
  display: grid;
  gap: 8px;
  padding: 16px;
  width: 100%;
  font: inherit;
  text-align: left;
  color: inherit;
  background: rgba(8, 20, 33, 0.78);
  border: 1px solid rgba(106, 167, 255, 0.14);
  border-radius: 18px;
  appearance: none;
  cursor: pointer;
  scroll-snap-align: start;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.stats-gallery__group-chip:hover {
  transform: translateY(-2px);
  border-color: rgba(127, 228, 208, 0.3);
}

.stats-gallery__group-chip--active {
  border-color: rgba(127, 228, 208, 0.56);
  box-shadow: 0 18px 32px rgba(4, 12, 22, 0.24);
}

.stats-gallery__group-chip span {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.stats-gallery__group-focus {
  padding: 18px;
  border-radius: 20px;
  background: rgba(8, 20, 33, 0.68);
  border: 1px solid rgba(127, 228, 208, 0.12);
}

.stats-gallery__item-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(8, 20, 33, 0.88);
  border: 1px solid rgba(106, 167, 255, 0.14);
  scroll-snap-align: start;
}

.stats-gallery__preview {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  aspect-ratio: 4 / 3;
  max-height: clamp(160px, 18vw, 220px);
  padding: 12px;
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
  .stats-gallery__selector-header,
  .stats-gallery__group-focus-header,
  .stats-gallery__item-title {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-gallery__metrics {
    grid-template-columns: minmax(0, 1fr);
  }

  .stats-gallery__group-rail {
    grid-auto-columns: minmax(200px, 78vw);
  }

  .stats-gallery__sample-rail {
    grid-auto-columns: minmax(260px, 84vw);
  }
}
</style>
