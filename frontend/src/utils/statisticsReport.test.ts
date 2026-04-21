import { describe, expect, it } from "vitest";

import type { StatisticsAIAnalysisResponse, StatisticsOverview } from "@/types/models";

import type { StatisticsReportPayload } from "./statisticsReport";
import { buildStatisticsPosterSvg } from "./statisticsReport";

/**
 * 构造统计图片导出测试所需的基础概览数据。
 * 这里保持数据量适中，重点验证海报图的固定高度和摘要裁剪逻辑。
 */
function buildOverview(): StatisticsOverview {
  return {
    filters: {
      startDate: "2026-04-01",
      endDate: "2026-04-21",
      days: 21,
      partId: null,
      deviceId: null,
    },
    summary: {
      totalCount: 128,
      goodCount: 102,
      badCount: 18,
      uncertainCount: 8,
      reviewedCount: 90,
      pendingReviewCount: 38,
      passRate: 102 / 128,
    },
    dailyTrend: [
      { date: "2026-04-18", totalCount: 22, goodCount: 18, badCount: 3, uncertainCount: 1 },
      { date: "2026-04-19", totalCount: 28, goodCount: 22, badCount: 4, uncertainCount: 2 },
      { date: "2026-04-20", totalCount: 34, goodCount: 27, badCount: 5, uncertainCount: 2 },
      { date: "2026-04-21", totalCount: 44, goodCount: 35, badCount: 6, uncertainCount: 3 },
    ],
    defectDistribution: [
      { defectType: "冲压毛刺", count: 11 },
      { defectType: "压痕", count: 6 },
      { defectType: "表面划伤", count: 4 },
      { defectType: "边缘缺口", count: 3 },
    ],
    resultDistribution: [
      { result: "good", count: 102 },
      { result: "bad", count: 18 },
      { result: "uncertain", count: 8 },
    ],
    reviewStatusDistribution: [
      { reviewStatus: "pending", count: 38 },
      { reviewStatus: "reviewed", count: 88 },
      { reviewStatus: "ai_reserved", count: 2 },
    ],
    partQualityRanking: [
      { partId: 1, partCode: "PART-001", partName: "垫片", totalCount: 48, goodCount: 36, badCount: 9, uncertainCount: 3, passRate: 0.75 },
      { partId: 2, partCode: "PART-002", partName: "冲压圈", totalCount: 30, goodCount: 23, badCount: 5, uncertainCount: 2, passRate: 0.767 },
      { partId: 3, partCode: "PART-003", partName: "连接片", totalCount: 26, goodCount: 21, badCount: 3, uncertainCount: 2, passRate: 0.808 },
      { partId: 4, partCode: "PART-004", partName: "卡扣件", totalCount: 24, goodCount: 22, badCount: 1, uncertainCount: 1, passRate: 0.917 },
    ],
    deviceQualityRanking: [
      { deviceId: 1, deviceCode: "MP157-001", deviceName: "主检设备 1", totalCount: 52, goodCount: 40, badCount: 8, uncertainCount: 4, passRate: 0.769 },
      { deviceId: 2, deviceCode: "MP157-002", deviceName: "主检设备 2", totalCount: 31, goodCount: 24, badCount: 5, uncertainCount: 2, passRate: 0.774 },
      { deviceId: 3, deviceCode: "MP157-003", deviceName: "主检设备 3", totalCount: 25, goodCount: 20, badCount: 3, uncertainCount: 2, passRate: 0.8 },
      { deviceId: 4, deviceCode: "MP157-004", deviceName: "主检设备 4", totalCount: 20, goodCount: 18, badCount: 2, uncertainCount: 0, passRate: 0.9 },
    ],
    keyFindings: [
      "冲压毛刺仍是不良的主要来源，优先检查刀口和送料稳定性。",
      "设备 1 的待确认占比偏高，建议先核查该设备治具和补光。",
      "过去两天检测总量上升较快，当前审核积压也同步增加。",
      "垫片类零件仍是主要风险来源，需要优先安排人工复核。",
    ],
    sampleGallery: {
      totalRecordCount: 64,
      totalImageCount: 192,
      totalPartCount: 4,
      latestUploadedAt: "2026-04-21T08:30:00.000Z",
      groups: [],
    },
    generatedAt: "2026-04-21T08:40:00.000Z",
  };
}

/**
 * 构造测试用 AI 主分析。
 */
function buildAiAnalysis(answer: string): StatisticsAIAnalysisResponse {
  return {
    status: "completed",
    answer,
    providerHint: "DeepSeek 官方",
    generatedAt: "2026-04-21T08:42:00.000Z",
  };
}

describe("statistics poster svg", () => {
  it("会输出固定高度的海报图，而不是无限增高的长图", () => {
    const payload: StatisticsReportPayload = {
      overview: buildOverview(),
      aiAnalysis: buildAiAnalysis("这是用于验证海报图高度的 AI 摘要。"),
      aiConversation: [],
      partLabel: "垫片 / PART-001",
      deviceLabel: "主检设备 1 / MP157-001",
    };

    const svg = buildStatisticsPosterSvg(payload);

    expect(svg).toContain('width="1600"');
    expect(svg).toContain('height="1880"');
    expect(svg).toContain("产品批次统计海报");
  });

  it("会把超长 AI 分析裁剪为摘要，并提示完整内容去看 PDF", () => {
    const payload: StatisticsReportPayload = {
      overview: buildOverview(),
      aiAnalysis: buildAiAnalysis("这是一段非常长的 AI 分析内容。".repeat(120)),
      aiConversation: [
        { localId: "msg-1", role: "user", content: "先看哪个设备？", createdAt: "2026-04-21T08:43:00.000Z" },
        { localId: "msg-2", role: "assistant", content: "建议先看主检设备 1，因为当前待确认和不良更集中。", createdAt: "2026-04-21T08:43:08.000Z" },
        { localId: "msg-3", role: "user", content: "那零件侧优先看什么？", createdAt: "2026-04-21T08:44:00.000Z" },
      ],
    };

    const svg = buildStatisticsPosterSvg(payload);

    expect(svg).toContain("完整 AI 全文、追问记录与审计留档建议导出 PDF");
    expect(svg).toContain("最近追问摘要");
    expect(svg).toContain("那零件侧优先看什么？");
    expect(svg).not.toContain("这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。这是一段非常长的 AI 分析内容。");
  });
});
