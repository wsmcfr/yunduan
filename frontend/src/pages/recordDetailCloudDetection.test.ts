import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * 读取检测详情页源码。
 *
 * 主要流程：
 * 1. 基于 Vitest 当前工作目录定位 `RecordDetailPage.vue`；
 * 2. 读取源码文本；
 * 3. 交给源码契约断言检查按钮、状态和上下文展示是否仍然存在。
 *
 * 返回:
 *   检测详情页 SFC 源码文本。
 */
function readRecordDetailSource(): string {
  return readFileSync(resolve(process.cwd(), "src/pages/RecordDetailPage.vue"), "utf8");
}

describe("record detail cloud detection contracts", () => {
  it("详情页提供手动云端检测按钮和云端模型上下文面板", () => {
    const source = readRecordDetailSource();

    expect(source).toContain("云端模型检测上下文");
    expect(source).toContain("重新进行云端检测");
    expect(source).toContain("cloudDetectionSubmitting");
    expect(source).toContain("handleRunCloudDetection");
    expect(source).toContain("runCloudDetection");
  });

  it("详情页展示云端检测生成图，便于和板端上传图片对比", () => {
    const source = readRecordDetailSource();

    expect(source).toContain("cloudGeneratedFiles");
    expect(source).toContain("云端检测生成图");
    expect(source).toContain("generated_files");
    expect(source).toContain("previewUrl");
  });
});
