import { describe, expect, it } from "vitest";

import type { PartModel } from "@/types/models";

import {
  UNCATEGORIZED_PART_CATEGORY_LABEL,
  buildPartCategoryKey,
  groupPartsByCategory,
  normalizePartCategoryLabel,
} from "./partCategories";

/**
 * 构造零件类型假数据，便于验证分类入口聚合逻辑。
 */
function createPart(
  overrides: Partial<PartModel> & Pick<PartModel, "id" | "partCode" | "name">,
): PartModel {
  return {
    id: overrides.id,
    partCode: overrides.partCode,
    name: overrides.name,
    category: overrides.category ?? null,
    description: overrides.description ?? null,
    isActive: overrides.isActive ?? true,
    recordCount: overrides.recordCount ?? 0,
    imageCount: overrides.imageCount ?? 0,
    deviceCount: overrides.deviceCount ?? 0,
    latestSourceDevice: overrides.latestSourceDevice ?? null,
    latestCapturedAt: overrides.latestCapturedAt ?? null,
    latestUploadedAt: overrides.latestUploadedAt ?? null,
    createdAt: overrides.createdAt ?? "2026-04-01T00:00:00Z",
    updatedAt: overrides.updatedAt ?? "2026-04-01T00:00:00Z",
  };
}

describe("part category helpers", () => {
  it("空分类会回退到未分类文案", () => {
    expect(normalizePartCategoryLabel("")).toBe(UNCATEGORIZED_PART_CATEGORY_LABEL);
    expect(normalizePartCategoryLabel(null)).toBe(UNCATEGORIZED_PART_CATEGORY_LABEL);
  });

  it("会按分类聚合零件类型并保留最新来源设备", () => {
    const entries = groupPartsByCategory([
      createPart({
        id: 1,
        partCode: "PART-001",
        name: "垫片 A",
        category: "垫片",
        recordCount: 3,
        imageCount: 6,
        latestUploadedAt: "2026-04-20T10:00:00Z",
        latestSourceDevice: {
          id: 1,
          deviceCode: "MP157-01",
          name: "主检测机",
        },
      }),
      createPart({
        id: 2,
        partCode: "PART-002",
        name: "垫片 B",
        category: "垫片",
        recordCount: 2,
        imageCount: 4,
        latestUploadedAt: "2026-04-20T12:00:00Z",
        latestSourceDevice: {
          id: 2,
          deviceCode: "MP157-02",
          name: "备检测机",
        },
      }),
      createPart({
        id: 3,
        partCode: "PART-003",
        name: "端子 A",
        category: "端子",
        recordCount: 1,
        imageCount: 2,
        latestUploadedAt: "2026-04-19T08:00:00Z",
      }),
    ]);

    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({
      key: buildPartCategoryKey("垫片"),
      label: "垫片",
      totalParts: 2,
      activeParts: 2,
      recordCount: 5,
      imageCount: 10,
      latestUploadedAt: "2026-04-20T12:00:00Z",
      latestSourceDevice: {
        deviceCode: "MP157-02",
      },
    });
    expect(entries[0]?.parts.map((item) => item.partCode)).toEqual(["PART-002", "PART-001"]);
  });

  it("空列表时返回空数组", () => {
    expect(groupPartsByCategory([])).toEqual([]);
  });
});
