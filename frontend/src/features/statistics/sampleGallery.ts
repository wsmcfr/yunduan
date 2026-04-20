import type { StatisticsFilters, StatisticsPartImageGroup, StatisticsSampleGallery } from "@/types/models";

/**
 * “全部图片”入口使用的固定 key。
 * 单独导出后，组件和测试都能共用同一份入口标识。
 */
export const SAMPLE_GALLERY_ALL_ENTRY_KEY = "all";

/**
 * 当零件没有分类时，统计页统一回退到这个分类文案。
 */
export const UNCATEGORIZED_SAMPLE_GALLERY_LABEL = "未分类";

/**
 * 统计页按分类聚合后的入口状态。
 * 每个入口下仍然保留零件分组，避免把多个零件直接糅成一团。
 */
export interface StatisticsSampleGalleryCategoryEntry {
  key: string;
  label: string;
  groupCount: number;
  recordCount: number;
  imageCount: number;
  latestUploadedAt: string | null;
  groups: StatisticsPartImageGroup[];
}

/**
 * 统一比较两个可空时间字符串。
 * 返回负数表示 left 更新、更应该排在前面。
 */
function compareNullableDateDesc(left: string | null, right: string | null): number {
  const leftTimestamp = left ? Date.parse(left) : 0;
  const rightTimestamp = right ? Date.parse(right) : 0;
  return rightTimestamp - leftTimestamp;
}

/**
 * 生成分类入口的稳定 key。
 * 这里不直接使用数组索引，避免分类顺序变化时选中态错位。
 */
export function buildSampleGalleryCategoryEntryKey(label: string): string {
  return `category:${label}`;
}

/**
 * 把当前统计筛选条件转换成独立图库页可复用的路由查询参数。
 * 这样统计页和零件类型页都能稳定跳到同一套图库入口。
 */
export function buildStatisticsGalleryRouteQuery(
  filters: StatisticsFilters,
  categoryLabel?: string | null,
): Record<string, string> {
  const query: Record<string, string> = {
    days: String(filters.days),
  };

  if (filters.startDate) {
    query.start_date = filters.startDate;
  }
  if (filters.endDate) {
    query.end_date = filters.endDate;
  }
  if (filters.partId !== null) {
    query.part_id = String(filters.partId);
  }
  if (filters.deviceId !== null) {
    query.device_id = String(filters.deviceId);
  }
  if (categoryLabel && categoryLabel.trim()) {
    query.category = categoryLabel.trim();
  }

  return query;
}

/**
 * 归一化零件分类名称，确保空值时仍能稳定归入“未分类”入口。
 */
export function normalizeSampleGalleryCategoryLabel(category: string | null | undefined): string {
  const normalizedLabel = category?.trim();
  return normalizedLabel ? normalizedLabel : UNCATEGORIZED_SAMPLE_GALLERY_LABEL;
}

/**
 * 把后端按零件分组的图库摘要，整理成前端按“分类入口”展示的结构。
 * 这样统计页就能同时提供“全部图片”入口和“按类别进入”的入口。
 */
export function groupSampleGalleryByCategory(
  gallery: StatisticsSampleGallery | null,
): StatisticsSampleGalleryCategoryEntry[] {
  if (!gallery || gallery.groups.length === 0) {
    return [];
  }

  const categoryBucket = new Map<string, StatisticsSampleGalleryCategoryEntry>();

  for (const group of gallery.groups) {
    const categoryLabel = normalizeSampleGalleryCategoryLabel(group.partCategory);
    const entryKey = buildSampleGalleryCategoryEntryKey(categoryLabel);
    const existingEntry = categoryBucket.get(entryKey);

    if (!existingEntry) {
      categoryBucket.set(entryKey, {
        key: entryKey,
        label: categoryLabel,
        groupCount: 1,
        recordCount: group.recordCount,
        imageCount: group.imageCount,
        latestUploadedAt: group.latestUploadedAt,
        groups: [group],
      });
      continue;
    }

    existingEntry.groupCount += 1;
    existingEntry.recordCount += group.recordCount;
    existingEntry.imageCount += group.imageCount;
    if (compareNullableDateDesc(group.latestUploadedAt, existingEntry.latestUploadedAt) < 0) {
      existingEntry.latestUploadedAt = group.latestUploadedAt;
    }
    existingEntry.groups.push(group);
  }

  return Array.from(categoryBucket.values())
    .map((entry) => ({
      ...entry,
      groups: [...entry.groups].sort((left, right) => {
        const uploadDiff = compareNullableDateDesc(left.latestUploadedAt, right.latestUploadedAt);
        if (uploadDiff !== 0) {
          return uploadDiff;
        }
        if (left.recordCount !== right.recordCount) {
          return right.recordCount - left.recordCount;
        }
        return left.partCode.localeCompare(right.partCode, "zh-CN");
      }),
    }))
    .sort((left, right) => {
      const uploadDiff = compareNullableDateDesc(left.latestUploadedAt, right.latestUploadedAt);
      if (uploadDiff !== 0) {
        return uploadDiff;
      }
      if (left.recordCount !== right.recordCount) {
        return right.recordCount - left.recordCount;
      }
      return left.label.localeCompare(right.label, "zh-CN");
    });
}
