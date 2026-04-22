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
  type StatisticsSampleGalleryCategoryEntry,
} from "./sampleGallery";

/**
 * 分类详情页里每次展示的零件分组数量。
 * 分组太多时改成分页网格，而不是继续横向长轨道。
 */
const GROUPS_PER_PAGE = 6;

/**
 * 单个零件分组下每页展示的样本卡片数量。
 * 控制详情区长度，避免一页堆满大量复检入口。
 */
const SAMPLES_PER_PAGE = 4;

/**
 * 图库页内分页工作区。
 * 先看分类入口，再看分类内零件类型，最后看具体样本卡片，避免全部内容堆成一条长页面。
 */
type GalleryWorkspacePage = "overview" | "groups" | "samples";

/**
 * 图库分页导航配置。
 * 这里把每一页的职责写清楚，让用户知道下一页到底会看到什么。
 */
const GALLERY_WORKSPACE_PAGE_OPTIONS: Array<{
  name: GalleryWorkspacePage;
  title: string;
  description: string;
}> = [
  {
    name: "overview",
    title: "分类入口",
    description: "先看有哪些零件分类可进入。",
  },
  {
    name: "groups",
    title: "零件类型",
    description: "在分类内继续筛选零件类型。",
  },
  {
    name: "samples",
    title: "样本复检",
    description: "查看样本卡片并进入复检详情。",
  },
];

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
 * 默认先落在“全部分类”入口，让图库页先承担分类导航角色，而不是一进来就铺开所有图片。
 */
const activeEntryKey = ref(SAMPLE_GALLERY_ALL_ENTRY_KEY);

/**
 * 当前分类详情里选中的零件分组。
 * 用户进入某个分类后，只围绕一个分组继续看分页样本，减少干扰。
 */
const activeGroupId = ref<number | null>(null);

/**
 * 分类详情区的分页状态。
 * 一个负责“零件分组页”，一个负责“样本页”。
 */
const groupPage = ref(1);
const samplePage = ref(1);
const activeWorkspacePage = ref<GalleryWorkspacePage>("overview");

/**
 * 把图库按零件分类整理成入口列表。
 */
const categoryEntries = computed(() => groupSampleGalleryByCategory(props.gallery));

/**
 * 当前是否存在任何可展示的样本图记录。
 */
const hasGallery = computed(() => (props.gallery?.totalRecordCount ?? 0) > 0);

/**
 * 当前正在查看的分类入口。
 * “全部分类”模式下返回空值，页面会渲染分类索引卡片。
 */
const activeEntry = computed<StatisticsSampleGalleryCategoryEntry | null>(() => {
  if (activeEntryKey.value === SAMPLE_GALLERY_ALL_ENTRY_KEY) {
    return null;
  }

  return categoryEntries.value.find((item) => item.key === activeEntryKey.value) ?? null;
});

/**
 * 当前分类详情里选中的零件分组。
 */
const activeGroup = computed<StatisticsPartImageGroup | null>(() => {
  if (!activeEntry.value) {
    return null;
  }

  return activeEntry.value.groups.find((group) => group.partId === activeGroupId.value)
    ?? activeEntry.value.groups[0]
    ?? null;
});

/**
 * 当前分类下零件分组的总页数与实际生效页码。
 * 如果分类切换后分组数量减少，这里会自动把页码夹回有效范围。
 */
const groupPageCount = computed(() =>
  Math.max(Math.ceil((activeEntry.value?.groups.length ?? 0) / GROUPS_PER_PAGE), 1),
);
const normalizedGroupPage = computed(() =>
  Math.min(groupPage.value, groupPageCount.value),
);

/**
 * 当前页可见的零件分组。
 */
const visibleGroups = computed(() => {
  const groups = activeEntry.value?.groups ?? [];
  const startIndex = (normalizedGroupPage.value - 1) * GROUPS_PER_PAGE;
  return groups.slice(startIndex, startIndex + GROUPS_PER_PAGE);
});

/**
 * 当前零件分组下样本卡片的总页数与实际页码。
 */
const samplePageCount = computed(() =>
  Math.max(Math.ceil((activeGroup.value?.items.length ?? 0) / SAMPLES_PER_PAGE), 1),
);
const normalizedSamplePage = computed(() =>
  Math.min(samplePage.value, samplePageCount.value),
);

/**
 * 当前图库页码信息。
 */
const activeWorkspacePageIndex = computed(() =>
  Math.max(
    GALLERY_WORKSPACE_PAGE_OPTIONS.findIndex((item) => item.name === activeWorkspacePage.value),
    0,
  ),
);

/**
 * 当前页配置。
 */
const activeWorkspacePageConfig = computed(() =>
  GALLERY_WORKSPACE_PAGE_OPTIONS[activeWorkspacePageIndex.value]
    ?? GALLERY_WORKSPACE_PAGE_OPTIONS[0],
);

/**
 * 当前页真正展示的样本卡片。
 */
const visibleSampleItems = computed(() => {
  const items = activeGroup.value?.items ?? [];
  const startIndex = (normalizedSamplePage.value - 1) * SAMPLES_PER_PAGE;
  return items.slice(startIndex, startIndex + SAMPLES_PER_PAGE);
});

/**
 * 当前入口下方的说明文字。
 */
const activeEntryHint = computed(() => {
  if (!hasGallery.value || !props.gallery) {
    return "当前筛选窗口内还没有可用于统计展示的样本图片。";
  }

  if (activeEntryKey.value === SAMPLE_GALLERY_ALL_ENTRY_KEY) {
    return `总入口当前汇总了 ${categoryEntries.value.length} 个零件分类。先进入分类，再查看该分类下的零件类型和复检入口，会比把全部图片一口气铺满更清晰。`;
  }

  if (!activeEntry.value) {
    return "当前入口对应的分类已不存在，已自动回退到全部分类入口。";
  }

  return `当前正在查看“${activeEntry.value.label}”分类。下方先按页展示零件类型，再按页展示该零件类型下的样本记录。`;
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
 * 入口切换后，自动为详情区选中一个有效分组，并把分页重置回第一页。
 * 这样用户每次进入分类时都会落在该分类最新的分组上，不会看到空页。
 */
watch(
  () => [activeEntry.value?.key ?? "none", activeEntry.value?.groups.map((group) => group.partId).join("|")],
  () => {
    if (!activeEntry.value) {
      activeGroupId.value = null;
      groupPage.value = 1;
      samplePage.value = 1;
      activeWorkspacePage.value = "overview";
      return;
    }

    const nextGroup = activeEntry.value.groups.find((group) => group.partId === activeGroupId.value)
      ?? activeEntry.value.groups[0]
      ?? null;

    activeGroupId.value = nextGroup?.partId ?? null;
    groupPage.value = 1;
    samplePage.value = 1;

    if (activeWorkspacePage.value === "overview") {
      activeWorkspacePage.value = "groups";
    }
  },
  { immediate: true },
);

/**
 * 把页码限制到有效范围内。
 */
function clampPage(page: number, pageCount: number): number {
  return Math.min(Math.max(page, 1), Math.max(pageCount, 1));
}

/**
 * 进入指定分类入口。
 * 统一收口入口切换，保证详情区的分组和分页状态一起重置。
 */
function selectEntry(entryKey: string): void {
  activeEntryKey.value = entryKey;
  activeGroupId.value = null;
  groupPage.value = 1;
  samplePage.value = 1;
  activeWorkspacePage.value = entryKey === SAMPLE_GALLERY_ALL_ENTRY_KEY ? "overview" : "groups";
}

/**
 * 选择当前分类下的零件分组。
 * 切换分组后，样本分页总是从第一页开始，避免用户落到一个已经不存在的旧页码。
 */
function selectGroup(partId: number): void {
  if (!activeEntry.value) {
    return;
  }

  const targetIndex = activeEntry.value.groups.findIndex((group) => group.partId === partId);
  if (targetIndex < 0) {
    return;
  }

  activeGroupId.value = partId;
  groupPage.value = Math.floor(targetIndex / GROUPS_PER_PAGE) + 1;
  samplePage.value = 1;
  activeWorkspacePage.value = "samples";
}

/**
 * 切换零件分组页。
 * 如果翻页后原来选中的分组不在当前页内，就自动选中这一页的第一个分组。
 */
function changeGroupPage(nextPage: number): void {
  if (!activeEntry.value) {
    return;
  }

  const nextNormalizedPage = clampPage(nextPage, groupPageCount.value);
  groupPage.value = nextNormalizedPage;

  const startIndex = (nextNormalizedPage - 1) * GROUPS_PER_PAGE;
  const nextVisibleGroups = activeEntry.value.groups.slice(startIndex, startIndex + GROUPS_PER_PAGE);
  const currentGroupStillVisible = nextVisibleGroups.some((group) => group.partId === activeGroupId.value);

  if (!currentGroupStillVisible) {
    activeGroupId.value = nextVisibleGroups[0]?.partId ?? null;
    samplePage.value = 1;
  }
}

/**
 * 切换样本卡片分页。
 */
function changeSamplePage(nextPage: number): void {
  samplePage.value = clampPage(nextPage, samplePageCount.value);
}

/**
 * 直接切换图库工作区页面。
 */
function goToWorkspacePage(nextPage: GalleryWorkspacePage): void {
  activeWorkspacePage.value = nextPage;
}

/**
 * 顺序翻页。
 */
function stepWorkspacePage(direction: -1 | 1): void {
  const nextIndex = Math.min(
    Math.max(activeWorkspacePageIndex.value + direction, 0),
    GALLERY_WORKSPACE_PAGE_OPTIONS.length - 1,
  );
  activeWorkspacePage.value = GALLERY_WORKSPACE_PAGE_OPTIONS[nextIndex]?.name ?? "overview";
}

/**
 * 解析分类封面图。
 * 用该分类下最新分组的第一张预览图做入口卡封面，让总入口不再是一大片空白说明文字。
 */
function resolveCategoryPreviewUrl(entry: StatisticsSampleGalleryCategoryEntry): string | null {
  return entry.groups[0]?.items[0]?.previewUrl ?? null;
}

/**
 * 为分类封面生成替代文本。
 */
function buildCategoryPreviewAlt(entry: StatisticsSampleGalleryCategoryEntry): string {
  return `${entry.label} 分类封面图`;
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
          这里先按零件分类给出总入口，再进入分类内部查看零件类型和样本记录。页面不再把所有图片同时铺开，而是改成分类索引加分页详情。
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
        hint="先按分类入口组织，再进入分类内部查看"
        accent="success"
      />
      <MetricCard
        label="零件分组"
        :value="String(gallery?.totalPartCount ?? 0)"
        hint="按零件类型拆分后的具体分组数量"
        accent="warning"
      />
    </div>

    <ElEmpty
      v-if="!hasGallery"
      description="当前筛选窗口内还没有可展示的样本图片。"
    />

    <template v-else>
      <section class="stats-gallery__workspace-pager">
        <div class="stats-gallery__workspace-pager-header">
          <div>
            <strong>图库分页导航</strong>
            <p class="muted-text">
              图库页拆成三页：先选分类，再看零件类型，最后看样本卡片。这样每一页都只承担一种任务，不再上下拖很长。
            </p>
          </div>
          <ElTag effect="dark" round type="info">
            第 {{ activeWorkspacePageIndex + 1 }} / {{ GALLERY_WORKSPACE_PAGE_OPTIONS.length }} 页
          </ElTag>
        </div>

        <div class="stats-gallery__workspace-pager-grid">
          <button
            v-for="(item, index) in GALLERY_WORKSPACE_PAGE_OPTIONS"
            :key="item.name"
            type="button"
            class="stats-gallery__workspace-pager-item"
            :class="{ 'stats-gallery__workspace-pager-item--active': activeWorkspacePage === item.name }"
            @click="goToWorkspacePage(item.name)"
          >
            <span class="stats-gallery__workspace-pager-index">0{{ index + 1 }}</span>
            <strong>{{ item.title }}</strong>
            <span>{{ item.description }}</span>
          </button>
        </div>

        <div class="stats-gallery__workspace-pager-footer">
          <div>
            <strong>{{ activeWorkspacePageConfig.title }}</strong>
            <p class="muted-text">{{ activeWorkspacePageConfig.description }}</p>
          </div>
          <div class="stats-gallery__workspace-pager-actions">
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
              :disabled="activeWorkspacePageIndex >= GALLERY_WORKSPACE_PAGE_OPTIONS.length - 1"
              @click="stepWorkspacePage(1)"
            >
              下一页
            </ElButton>
          </div>
        </div>
      </section>

      <div class="stats-gallery__workspace-stage">
        <div
          class="stats-gallery__workspace-page"
          :class="{ 'stats-gallery__workspace-page--active': activeWorkspacePage === 'overview' }"
          data-workspace-page="overview"
        >
          <div class="stats-gallery__entry-bar">
            <ElButton
              round
              :type="activeEntryKey === SAMPLE_GALLERY_ALL_ENTRY_KEY ? 'primary' : 'default'"
              @click="selectEntry(SAMPLE_GALLERY_ALL_ENTRY_KEY)"
            >
              全部分类
            </ElButton>

            <ElButton
              v-for="entry in categoryEntries"
              :key="entry.key"
              round
              :type="activeEntryKey === entry.key ? 'primary' : 'default'"
              plain
              @click="selectEntry(entry.key)"
            >
              {{ entry.label }} · {{ entry.recordCount }}
            </ElButton>
          </div>

          <p class="stats-gallery__entry-hint muted-text">
            {{ activeEntryHint }}
          </p>

          <div class="stats-gallery__category-index">
            <article
              v-for="entry in categoryEntries"
              :key="entry.key"
              class="stats-gallery__category-card"
            >
              <div class="stats-gallery__category-preview">
                <img
                  v-if="resolveCategoryPreviewUrl(entry)"
                  :src="resolveCategoryPreviewUrl(entry) ?? undefined"
                  :alt="buildCategoryPreviewAlt(entry)"
                  class="stats-gallery__category-preview-image"
                  loading="lazy"
                >
                <div v-else class="stats-gallery__category-preview-fallback">
                  <strong>{{ entry.label }}</strong>
                  <span>{{ entry.imageCount }} 张图片</span>
                </div>
              </div>

              <div class="stats-gallery__category-card-body">
                <div class="stats-gallery__category-card-header">
                  <div>
                    <strong>{{ entry.label }}</strong>
                    <p class="muted-text">
                      {{ entry.groupCount }} 个零件分组，{{ entry.recordCount }} 条记录
                    </p>
                  </div>
                  <ElTag effect="dark" round type="info">
                    最近上传 {{ formatDateTime(entry.latestUploadedAt) }}
                  </ElTag>
                </div>

                <div class="stats-gallery__category-card-metrics">
                  <span>{{ entry.imageCount }} 张图片</span>
                  <span>{{ entry.groupCount }} 个类型</span>
                  <span>{{ entry.recordCount }} 条记录</span>
                </div>

                <div class="stats-gallery__category-card-actions">
                  <ElButton type="primary" plain @click="selectEntry(entry.key)">
                    查看该分类
                  </ElButton>
                </div>
              </div>
            </article>
          </div>
        </div>

        <div
          class="stats-gallery__workspace-page"
          :class="{ 'stats-gallery__workspace-page--active': activeWorkspacePage === 'groups' }"
          data-workspace-page="groups"
        >
          <section v-if="activeEntry" class="stats-gallery__category-section">
            <div class="stats-gallery__category-header">
              <div>
                <strong>{{ activeEntry.label }}</strong>
                <p class="muted-text">
                  共 {{ activeEntry.groupCount }} 个零件分组，{{ activeEntry.recordCount }} 条检测记录，{{ activeEntry.imageCount }} 张图片
                </p>
              </div>
              <div class="stats-gallery__category-header-actions">
                <ElTag effect="dark" round type="info">
                  最近上传 {{ formatDateTime(activeEntry.latestUploadedAt) }}
                </ElTag>
                <ElButton plain @click="selectEntry(SAMPLE_GALLERY_ALL_ENTRY_KEY)">
                  返回全部分类
                </ElButton>
              </div>
            </div>

            <div class="stats-gallery__selector-header">
              <div>
                <strong>分类内零件类型</strong>
                <p class="muted-text">先翻页查看这个分类下有哪些零件类型，再点进某个类型查看样本卡片。</p>
              </div>
              <div class="stats-gallery__selector-actions">
                <span class="muted-text">
                  第 {{ normalizedGroupPage }} / {{ groupPageCount }} 页
                </span>
                <ElButton
                  text
                  :disabled="normalizedGroupPage <= 1"
                  @click="changeGroupPage(normalizedGroupPage - 1)"
                >
                  上一页
                </ElButton>
                <ElButton
                  text
                  :disabled="normalizedGroupPage >= groupPageCount"
                  @click="changeGroupPage(normalizedGroupPage + 1)"
                >
                  下一页
                </ElButton>
              </div>
            </div>

            <div class="stats-gallery__group-grid">
              <button
                v-for="group in visibleGroups"
                :key="group.partId"
                type="button"
                class="stats-gallery__group-chip"
                :class="{
                  'stats-gallery__group-chip--active': activeGroup?.partId === group.partId,
                }"
                @click="selectGroup(group.partId)"
              >
                <strong>{{ group.partName }}</strong>
                <span>{{ group.partCode }}</span>
                <span>{{ group.recordCount }} 条记录 · {{ group.imageCount }} 张图片</span>
              </button>
            </div>
          </section>

          <ElEmpty
            v-else
            description="请先回到上一页选择一个零件分类。"
          />
        </div>

        <div
          class="stats-gallery__workspace-page"
          :class="{ 'stats-gallery__workspace-page--active': activeWorkspacePage === 'samples' }"
          data-workspace-page="samples"
        >
          <section v-if="activeGroup" class="stats-gallery__group-focus">
            <div class="stats-gallery__group-focus-header">
              <div>
                <strong>{{ activeGroup.partName }}</strong>
                <p class="muted-text">
                  {{ activeGroup.partCode }}
                  · {{ activeGroup.recordCount }} 条记录
                  · {{ activeGroup.imageCount }} 张图片
                </p>
              </div>
              <div class="stats-gallery__selector-actions">
                <span class="muted-text">
                  第 {{ normalizedSamplePage }} / {{ samplePageCount }} 页
                </span>
                <ElButton
                  text
                  @click="goToWorkspacePage('groups')"
                >
                  返回类型页
                </ElButton>
                <ElButton
                  text
                  :disabled="normalizedSamplePage <= 1"
                  @click="changeSamplePage(normalizedSamplePage - 1)"
                >
                  上一页
                </ElButton>
                <ElButton
                  text
                  :disabled="normalizedSamplePage >= samplePageCount"
                  @click="changeSamplePage(normalizedSamplePage + 1)"
                >
                  下一页
                </ElButton>
              </div>
            </div>

            <div class="stats-gallery__sample-grid">
              <article
                v-for="item in visibleSampleItems"
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

          <ElEmpty
            v-else
            description="请先在上一页选择一个零件类型。"
          />
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.stats-gallery,
.stats-gallery__metrics,
.stats-gallery__category-index,
.stats-gallery__item-body,
.stats-gallery__sample-grid,
.stats-gallery__workspace-stage,
.stats-gallery__workspace-page {
  display: grid;
  gap: 18px;
}

.stats-gallery {
  padding: 24px;
  align-content: start;
}

.stats-gallery__header,
.stats-gallery__workspace-pager-header,
.stats-gallery__workspace-pager-footer,
.stats-gallery__category-header,
.stats-gallery__selector-header,
.stats-gallery__group-focus-header,
.stats-gallery__item-title,
.stats-gallery__category-card-header,
.stats-gallery__category-card-actions,
.stats-gallery__category-header-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.stats-gallery__header p,
.stats-gallery__workspace-pager-header p,
.stats-gallery__workspace-pager-footer p,
.stats-gallery__category-header p,
.stats-gallery__selector-header p,
.stats-gallery__group-focus-header p,
.stats-gallery__category-card-header p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.stats-gallery__workspace-pager {
  display: grid;
  gap: 16px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(255, 255, 255, 0.02);
}

.stats-gallery__workspace-pager-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.stats-gallery__workspace-pager-item {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(149, 184, 223, 0.12);
  background: rgba(8, 20, 33, 0.78);
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.stats-gallery__workspace-pager-item:hover {
  transform: translateY(-1px);
  border-color: rgba(127, 228, 208, 0.28);
}

.stats-gallery__workspace-pager-item--active {
  border-color: rgba(127, 228, 208, 0.46);
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.12), transparent 38%),
    rgba(255, 255, 255, 0.04);
}

.stats-gallery__workspace-pager-index {
  color: rgba(127, 228, 208, 0.86);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.stats-gallery__workspace-pager-item strong {
  font-size: 15px;
  line-height: 1.4;
}

.stats-gallery__workspace-pager-item span {
  color: var(--app-text-secondary);
  line-height: 1.7;
  font-size: 13px;
}

.stats-gallery__workspace-pager-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

.stats-gallery__workspace-page {
  display: none;
  align-content: start;
}

.stats-gallery__workspace-page--active {
  display: grid;
}

.stats-gallery__metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stats-gallery__entry-bar,
.stats-gallery__selector-actions,
.stats-gallery__item-tags,
.stats-gallery__item-meta,
.stats-gallery__item-actions,
.stats-gallery__category-card-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.stats-gallery__entry-bar {
  gap: 12px;
}

.stats-gallery__entry-hint {
  margin: 0;
  line-height: 1.7;
}

.stats-gallery__category-index {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.stats-gallery__category-card,
.stats-gallery__category-section,
.stats-gallery__group-focus {
  display: grid;
  gap: 16px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(127, 228, 208, 0.12);
}

.stats-gallery__category-card,
.stats-gallery__group-focus {
  background:
    radial-gradient(circle at top right, rgba(127, 228, 208, 0.08), transparent 34%),
    rgba(255, 255, 255, 0.02);
}

.stats-gallery__category-section {
  background:
    linear-gradient(180deg, rgba(20, 40, 58, 0.82), rgba(11, 25, 39, 0.96));
}

.stats-gallery__category-preview,
.stats-gallery__preview {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 12px;
  border-radius: 16px;
  background:
    radial-gradient(circle at top left, rgba(127, 228, 208, 0.2), transparent 45%),
    linear-gradient(160deg, rgba(20, 45, 62, 0.96), rgba(8, 20, 33, 0.98));
}

.stats-gallery__category-preview {
  aspect-ratio: 16 / 10;
  max-height: 180px;
}

.stats-gallery__preview {
  aspect-ratio: 4 / 3;
  max-height: clamp(160px, 18vw, 220px);
}

.stats-gallery__category-preview-image,
.stats-gallery__preview-image {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
}

.stats-gallery__category-preview-fallback,
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

.stats-gallery__category-card-body {
  display: grid;
  gap: 14px;
}

.stats-gallery__category-card-metrics span {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--app-text-secondary);
  font-size: 12px;
}

.stats-gallery__group-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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

.stats-gallery__sample-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.stats-gallery__item-card {
  display: grid;
  gap: 14px;
  height: 100%;
  padding: 16px;
  border-radius: 20px;
  background: rgba(8, 20, 33, 0.88);
  border: 1px solid rgba(106, 167, 255, 0.14);
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
  .stats-gallery__metrics,
  .stats-gallery__sample-grid,
  .stats-gallery__workspace-pager-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-gallery__header,
  .stats-gallery__workspace-pager-header,
  .stats-gallery__workspace-pager-footer,
  .stats-gallery__category-header,
  .stats-gallery__selector-header,
  .stats-gallery__group-focus-header,
  .stats-gallery__item-title,
  .stats-gallery__category-card-header,
  .stats-gallery__category-card-actions,
  .stats-gallery__category-header-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-gallery__metrics,
  .stats-gallery__sample-grid,
  .stats-gallery__group-grid,
  .stats-gallery__category-index,
  .stats-gallery__workspace-pager-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media print {
  .stats-gallery__metrics,
  .stats-gallery__category-index,
  .stats-gallery__group-grid,
  .stats-gallery__sample-grid {
    grid-template-columns: 1fr !important;
  }

  .stats-gallery__workspace-pager,
  .stats-gallery__entry-bar,
  .stats-gallery__selector-actions,
  .stats-gallery__category-card-actions {
    display: none !important;
  }

  .stats-gallery__workspace-page {
    display: grid !important;
    break-before: page;
    page-break-before: always;
  }

  .stats-gallery__workspace-page:first-child {
    break-before: auto;
    page-break-before: auto;
  }

  .stats-gallery__header,
  .stats-gallery__category-header,
  .stats-gallery__group-focus-header,
  .stats-gallery__category-card-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
