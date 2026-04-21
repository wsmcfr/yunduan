import { describe, expect, it } from "vitest";

import {
  buildAiPreviewUrl,
  createAiOpeningMessage,
  sortAiDisplayFiles,
} from "./aiReview";

describe("ai review utilities", () => {
  it("可以从 COS 元数据拼出预览地址", () => {
    const previewUrl = buildAiPreviewUrl({
      previewUrl: null,
      objectKey: "detections/demo/source/raw image.png",
      bucketName: "demo-bucket-1250000000",
      region: "ap-guangzhou",
    });

    expect(previewUrl).toBe(
      "https://demo-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/detections/demo/source/raw%20image.png",
    );
  });

  it("遇到完整 URL 时直接返回原值", () => {
    const previewUrl = buildAiPreviewUrl({
      previewUrl: null,
      objectKey: "https://example.com/demo.png",
      bucketName: "ignored",
      region: "ignored",
    });

    expect(previewUrl).toBe("https://example.com/demo.png");
  });

  it("优先使用后端返回的签名预览地址", () => {
    const previewUrl = buildAiPreviewUrl({
      previewUrl: "https://signed.example.com/demo.png?token=abc",
      objectKey: "detections/demo/source/raw.png",
      bucketName: "demo-bucket-1250000000",
      region: "ap-guangzhou",
    });

    expect(previewUrl).toBe("https://signed.example.com/demo.png?token=abc");
  });

  it("会把标注图排到源图和缩略图前面", () => {
    const sortedFiles = sortAiDisplayFiles([
      { fileKind: "thumbnail", uploadedAt: "2026-04-20T02:00:03.000Z" },
      { fileKind: "source", uploadedAt: "2026-04-20T02:00:02.000Z" },
      { fileKind: "annotated", uploadedAt: "2026-04-20T02:00:01.000Z" },
    ]);

    expect(sortedFiles.map((item) => item.fileKind)).toEqual([
      "annotated",
      "source",
      "thumbnail",
    ]);
  });

  it("打开 AI 对话时会生成带记录上下文的首条引导语", () => {
    const openingMessage = createAiOpeningMessage({
      id: 1,
      recordNo: "REC-TEST-001",
      result: "uncertain",
      effectiveResult: "good",
      reviewStatus: "reviewed",
      surfaceResult: null,
      backlightResult: null,
      eddyResult: null,
      defectType: null,
      defectDesc: null,
      confidenceScore: 0.61,
      visionContext: null,
      sensorContext: null,
      decisionContext: null,
      deviceContext: null,
      capturedAt: "2026-04-20T02:00:01.000Z",
      detectedAt: "2026-04-20T02:00:02.000Z",
      uploadedAt: "2026-04-20T02:00:03.000Z",
      storageLastModified: null,
      createdAt: "2026-04-20T02:00:03.000Z",
      updatedAt: "2026-04-20T02:00:03.000Z",
      part: {
        id: 1,
        partCode: "PART-METAL-01",
        name: "金属垫片样件",
        category: "垫片",
      },
      device: {
        id: 1,
        deviceCode: "MP157-VIS-01",
        name: "主视觉节点",
      },
    });

    expect(openingMessage).toContain("REC-TEST-001");
    expect(openingMessage).toContain("金属垫片样件");
    expect(openingMessage).toContain("MP157-VIS-01");
  });
});
