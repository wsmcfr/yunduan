import type { PartModel } from "@/types/models";

/**
 * 当零件类型没有填写上层分类时，前端统一回退到这个分类文案。
 * 这样零件管理、检测记录和图库页都能稳定使用同一套分类入口。
 */
export const UNCATEGORIZED_PART_CATEGORY_LABEL = "未分类";

const PART_NAME_BY_CODE: Record<string, string> = {
  gasket: "波形垫圈",
  wave_washer: "波形垫圈",
  washer: "平垫圈",
  splitwasher: "弹性垫圈",
};

const WASHER_CATEGORY_ALIASES = new Set([
  "垫圈",
  "垫片",
  "弹性垫圈",
  "washer-family",
  "washer_family",
]);

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
  if (!normalizedValue) {
    return UNCATEGORIZED_PART_CATEGORY_LABEL;
  }
  return WASHER_CATEGORY_ALIASES.has(normalizedValue) ? "垫圈类" : normalizedValue;
}

/**
 * 归一化真实模型字段里的分类值。
 * 空分类仍保留为 null，避免编辑弹窗把“未分类”占位文案写回后端。
 */
export function normalizePartCategoryValue(category: string | null | undefined): string | null {
  const normalizedValue = category?.trim();
  if (!normalizedValue) {
    return null;
  }
  return WASHER_CATEGORY_ALIASES.has(normalizedValue) ? "垫圈类" : normalizedValue;
}

/**
 * 根据模型零件编码生成统一显示名。
 * 历史训练标签 `gasket` 实际代表波形垫圈，不能按英文词面翻译成“垫片”。
 */
export function resolvePartDisplayName(
  partCode: string | null | undefined,
  rawName: string | null | undefined,
): string {
  const normalizedCode = partCode?.trim().toLowerCase() ?? "";
  const mappedName = PART_NAME_BY_CODE[normalizedCode];
  if (mappedName) {
    return mappedName;
  }

  const normalizedName = rawName?.trim();
  return normalizedName || normalizedCode || "未知零件";
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
    const displayPart = {
      ...part,
      name: resolvePartDisplayName(part.partCode, part.name),
      category: label,
    };
    const existingEntry = categoryBucket.get(categoryKey);

    if (!existingEntry) {
      categoryBucket.set(categoryKey, {
        key: categoryKey,
        label,
        totalParts: 1,
        activeParts: displayPart.isActive ? 1 : 0,
        recordCount: displayPart.recordCount,
        imageCount: displayPart.imageCount,
        latestUploadedAt: displayPart.latestUploadedAt,
        latestSourceDevice: displayPart.latestSourceDevice,
        parts: [displayPart],
      });
      continue;
    }

    existingEntry.totalParts += 1;
    existingEntry.activeParts += displayPart.isActive ? 1 : 0;
    existingEntry.recordCount += displayPart.recordCount;
    existingEntry.imageCount += displayPart.imageCount;
    if (compareNullableDateDesc(displayPart.latestUploadedAt, existingEntry.latestUploadedAt) < 0) {
      existingEntry.latestUploadedAt = displayPart.latestUploadedAt;
      existingEntry.latestSourceDevice = displayPart.latestSourceDevice;
    }
    existingEntry.parts.push(displayPart);
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
