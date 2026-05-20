import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { ElMessage } from "element-plus";

import { useAuthStore } from "@/stores/auth";
import { useStatisticsOverview } from "@/composables/useStatisticsOverview";
import {
  streamStatisticsAiAnalysis,
  streamStatisticsAiChat,
} from "@/services/api/statistics";
import type {
  AIRuntimeModelOption,
  StatisticsOverview,
  UserProfile,
} from "@/types/models";

vi.mock("element-plus", () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock("@/services/api/devices", () => ({
  fetchDevices: vi.fn(),
}));

vi.mock("@/services/api/parts", () => ({
  fetchParts: vi.fn(),
}));

vi.mock("@/services/api/settings", () => ({
  fetchRuntimeAIModels: vi.fn(),
}));

vi.mock("@/services/api/statistics", () => ({
  downloadStatisticsPdf: vi.fn(),
  fetchStatisticsOverview: vi.fn(),
  streamStatisticsAiAnalysis: vi.fn(),
  streamStatisticsAiChat: vi.fn(),
}));

vi.mock("@/utils/statisticsReport", () => ({
  exportStatisticsReportPng: vi.fn(),
}));

const demoUser: UserProfile = {
  id: 1,
  username: "admin",
  email: "admin@example.com",
  displayName: "默认管理员",
  role: "admin",
  company: {
    id: 1,
    name: "演示公司",
    isActive: true,
    isSystemReserved: false,
  },
  isDefaultAdmin: true,
  adminApplicationStatus: "approved",
  isActive: true,
  canUseAiAnalysis: true,
  lastLoginAt: null,
  passwordChangedAt: null,
  createdAt: "2026-05-01T00:00:00Z",
  updatedAt: "2026-05-01T00:00:00Z",
};

const demoRuntimeModel: AIRuntimeModelOption = {
  id: 9,
  displayName: "统计分析模型",
  upstreamVendor: "codex",
  protocolType: "openai_responses",
  userAgent: null,
  modelIdentifier: "gpt-demo",
  supportsVision: true,
  supportsStream: true,
  gatewayId: 3,
  gatewayName: "主网关",
  gatewayVendor: "openclaudecode",
  baseUrl: "https://example.com/v1",
};

/**
 * 构造统计工作台测试所需的最小概览模型。
 * AI 发起前只需要确认概览已存在，因此这里保留完整字段但不填复杂排行数据。
 */
function createDemoOverview(): StatisticsOverview {
  return {
    filters: {
      startDate: null,
      endDate: null,
      days: 14,
      partId: null,
      deviceId: null,
    },
    summary: {
      totalCount: 8,
      goodCount: 5,
      badCount: 2,
      uncertainCount: 1,
      reviewedCount: 3,
      pendingReviewCount: 1,
      passRate: 0.625,
    },
    dailyTrend: [],
    defectDistribution: [],
    resultDistribution: [],
    reviewStatusDistribution: [],
    partQualityRanking: [],
    deviceQualityRanking: [],
    keyFindings: [],
    sampleGallery: {
      totalRecordCount: 0,
      totalImageCount: 0,
      totalPartCount: 0,
      latestUploadedAt: null,
      groups: [],
    },
    generatedAt: "2026-05-01T08:00:00Z",
  };
}

/**
 * 创建一个“账号有 AI 权限、后端已有可用模型、但用户清空了模型选择”的统计工作台。
 */
function createStatisticsWorkspaceWithoutSelectedModel() {
  setActivePinia(createPinia());
  const authStore = useAuthStore();
  authStore.currentUser = demoUser;

  const workspace = useStatisticsOverview();
  workspace.overview.value = createDemoOverview();
  workspace.runtimeModels.value = [demoRuntimeModel];
  workspace.selectedModelId.value = null;
  return workspace;
}

describe("useStatisticsOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("生成统计 AI 分析前必须先选择模型", async () => {
    const workspace = createStatisticsWorkspaceWithoutSelectedModel();

    await workspace.runAiAnalysis();

    expect(streamStatisticsAiAnalysis).not.toHaveBeenCalled();
    expect(ElMessage.warning).toHaveBeenCalledWith("请选择一个已启用的 AI 模型配置后再发起统计 AI 分析或追问。");
  });

  it("发送统计 AI 追问前必须先选择模型", async () => {
    const workspace = createStatisticsWorkspaceWithoutSelectedModel();
    workspace.aiQuestion.value = "当前批次最需要先处理什么？";

    await workspace.submitAiQuestion();

    expect(streamStatisticsAiChat).not.toHaveBeenCalled();
    expect(ElMessage.warning).toHaveBeenCalledWith("请选择一个已启用的 AI 模型配置后再发起统计 AI 分析或追问。");
  });

  it("没有可用模型时也不能发起统计 AI 预留请求", async () => {
    const workspace = createStatisticsWorkspaceWithoutSelectedModel();
    workspace.runtimeModels.value = [];

    await workspace.runAiAnalysis();

    expect(streamStatisticsAiAnalysis).not.toHaveBeenCalled();
    expect(ElMessage.warning).toHaveBeenCalledWith("请选择一个已启用的 AI 模型配置后再发起统计 AI 分析或追问。");
  });
});
