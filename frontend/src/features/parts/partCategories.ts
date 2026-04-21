import type { PartModel } from "@/types/models";

/**
 * 当零件类型没有填写上层分类时，前端统一回退到这个分类文案。
 * 这样零件管理、检测记录和图库页都能稳定使用同一套分类入口。
 */
export const UNCATEGORIZED_PART_CATEGORY_LABEL = "未分类";

export interface PartCategorySummary {
  key: string;
  label: string;
  totalParts: number;
  activeParts: number;
  recordCount: number;
  imageCount: number;
  latestUploadedAt: string | null;
  latestSourceDevice: PartModel["latestSourceDevice"];
  parts: PartModel[];
}

/**
 * 归一化零件分类名称，避免空值导致入口文案和 key 漂移。
 */
export function normalizePartCategoryLabel(category: string | null | undefined): string {
  const normalizedValue = category?.trim();
  return normalizedValue ? normalizedValue : UNCATEGORIZED_PART_CATEGORY_LABEL;
}

/**
 * 生成零件分类的稳定 key。
 * 不使用数组索引，避免列表排序变化时选中态错位。
 */
export function buildPartCategoryKey(label: string): string {
  return `part-category:${label}`;
}

/**
 * 统一比较两个可空时间字符串，返回负数表示 left 更晚。
 */
function compareNullableDateDesc(left: string | null, right: string | null): number {
  const leftTimestamp = left ? Date.parse(left) : 0;
  const rightTimestamp = right ? Date.parse(right) : 0;
  return rightTimestamp - leftTimestamp;
}

/**
 * 把零件类型列表聚合成“分类入口 + 分类下类型明细”结构。
 * 零件管理和检测记录页都先按分类引导，再进入具体类型或记录。
 */
export function groupPartsByCategory(parts: PartModel[]): PartCategorySummary[] {
  if (parts.length === 0) {
    return [];
  }

  const categoryBucket = new Map<string, PartCategorySummary>();

  for (const part of parts) {
    const label = normalizePartCategoryLabel(part.category);
    const categoryKey = buildPartCategoryKey(label);
    const existingEntry = categoryBucket.get(categoryKey);

    if (!existingEntry) {
      categoryBucket.set(categoryKey, {
        key: categoryKey,
        label,
        totalParts: 1,
        activeParts: part.isActive ? 1 : 0,
        recordCount: part.recordCount,
        imageCount: part.imageCount,
        latestUploadedAt: part.latestUploadedAt,
        latestSourceDevice: part.latestSourceDevice,
        parts: [part],
      });
      continue;
    }

    existingEntry.totalParts += 1;
    existingEntry.activeParts += part.isActive ? 1 : 0;
    existingEntry.recordCount += part.recordCount;
    existingEntry.imageCount += part.imageCount;
    if (compareNullableDateDesc(part.latestUploadedAt, existingEntry.latestUploadedAt) < 0) {
      existingEntry.latestUploadedAt = part.latestUploadedAt;
      existingEntry.latestSourceDevice = part.latestSourceDevice;
    }
    existingEntry.parts.push(part);
  }

  return Array.from(categoryBucket.values())
    .map((entry) => ({
      ...entry,
      parts: [...entry.parts].sort((left, right) => {
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
