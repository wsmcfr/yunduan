import { describe, expect, it } from "vitest";

import type { StatisticsPartImageGroup, StatisticsSampleGallery } from "@/types/models";

import {
  SAMPLE_GALLERY_ALL_ENTRY_KEY,
  UNCATEGORIZED_SAMPLE_GALLERY_LABEL,
  buildSampleGalleryCategoryEntryKey,
  groupSampleGalleryByCategory,
  normalizeSampleGalleryCategoryLabel,
} from "./sampleGallery";

/**
 * 构造统计页图库中的零件分组假数据。
 * 测试只关心分类入口聚合，因此这里保留最小必要字段。
 */
function createGalleryGroup(
  overrides: Partial<StatisticsPartImageGroup> & Pick<StatisticsPartImageGroup, "partId" | "partCode" | "partName">,
): StatisticsPartImageGroup {
  return {
    partId: overrides.partId,
    partCode: overrides.partCode,
    partName: overrides.partName,
    partCategory: overrides.partCategory ?? null,
    recordCount: overrides.recordCount ?? 1,
    imageCount: overrides.imageCount ?? 1,
    latestUploadedAt: overrides.latestUploadedAt ?? null,
    items: overrides.items ?? [],
  };
}

/**
 * 构造图库响应假数据，便于验证分类入口聚合逻辑。
 */
function createGallery(groups: StatisticsPartImageGroup[]): StatisticsSampleGallery {
  return {
    totalRecordCount: groups.reduce((sum, item) => sum + item.recordCount, 0),
    totalImageCount: groups.reduce((sum, item) => sum + item.imageCount, 0),
    totalPartCount: groups.length,
    latestUploadedAt: groups[0]?.latestUploadedAt ?? null,
    groups,
  };
}

describe("statistics sample gallery helpers", () => {
  it("暴露统一的全部图片入口 key", () => {
    expect(SAMPLE_GALLERY_ALL_ENTRY_KEY).toBe("all");
  });

  it("空分类会回退到未分类文案", () => {
    expect(normalizeSampleGalleryCategoryLabel("")).toBe(UNCATEGORIZED_SAMPLE_GALLERY_LABEL);
    expect(normalizeSampleGalleryCategoryLabel(null)).toBe(UNCATEGORIZED_SAMPLE_GALLERY_LABEL);
  });

  it("会按分类聚合多个零件分组，并累加记录和图片数量", () => {
    const gallery = createGallery([
      createGalleryGroup({
        partId: 1,
        partCode: "PART-001",
        partName: "垫片 A",
        partCategory: "垫片",
        recordCount: 2,
        imageCount: 5,
        latestUploadedAt: "2026-04-20T10:00:00Z",
      }),
      createGalleryGroup({
        partId: 2,
        partCode: "PART-002",
        partName: "垫片 B",
        partCategory: "垫片",
        recordCount: 3,
        imageCount: 4,
        latestUploadedAt: "2026-04-20T12:00:00Z",
      }),
      createGalleryGroup({
        partId: 3,
        partCode: "PART-003",
        partName: "螺母 A",
        partCategory: "螺母",
        recordCount: 1,
        imageCount: 2,
        latestUploadedAt: "2026-04-19T09:00:00Z",
      }),
    ]);

    const categoryEntries = groupSampleGalleryByCategory(gallery);

    expect(categoryEntries).toHaveLength(2);
    expect(categoryEntries[0]).toMatchObject({
      key: buildSampleGalleryCategoryEntryKey("垫片"),
      label: "垫片",
      groupCount: 2,
      recordCount: 5,
      imageCount: 9,
      latestUploadedAt: "2026-04-20T12:00:00Z",
    });
    expect(categoryEntries[0]?.groups.map((item) => item.partCode)).toEqual(["PART-002", "PART-001"]);
  });

  it("没有任何图库数据时返回空数组", () => {
    expect(groupSampleGalleryByCategory(null)).toEqual([]);
    expect(groupSampleGalleryByCategory(createGallery([]))).toEqual([]);
  });
});
