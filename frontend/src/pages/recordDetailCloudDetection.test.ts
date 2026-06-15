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
    expect(source).toContain("visibleCloudGeneratedFiles");
    expect(source).toContain("CLOUD_GENERATED_IMAGE_PAGE_SIZE");
    expect(source).toContain("cloudGeneratedImagePageState");
    expect(source).toContain("changeCloudGeneratedImagePage");
    expect(source).toContain("云端检测生成图");
    expect(source).toContain(
      '<section class="app-panel detail-section detail-section--cloud-generated">\n        <div class="detail-section__header">\n          <div>\n            <strong>云端检测生成图</strong>',
    );
    expect(source).toContain("generated_files");
    expect(source).toContain("previewUrl");
    expect(source).toContain("cloud-generated-pager");
    expect(source).toContain("detail-section--cloud-generated");
    expect(source).toContain("height: 640px;");
    expect(source).toContain("grid-template-rows: auto minmax(0, 1fr);");
    expect(source).toContain("max-height: 100%;");
    expect(source).toContain("height: 100%;");
    expect(source).toContain("min-height: 42px;");
    expect(source).toContain("max-height: 42px;");
    expect(source).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(source).toContain("grid-auto-rows: 1fr;");
  });

  it("上下文卡片固定尺寸，长内容只能在卡片内部分页查看", () => {
    const source = readRecordDetailSource();

    expect(source).toContain("CONTEXT_VALUE_PAGE_SIZE");
    expect(source).toContain("CONTEXT_PANEL_PAGE_SIZE");
    expect(source).toContain("contextValuePageState");
    expect(source).toContain("contextPanelPageState");
    expect(source).toContain("getContextValuePage");
    expect(source).toContain("getContextPanelPage");
    expect(source).toContain("changeContextValuePage");
    expect(source).toContain("changeContextPanelPage");
    expect(source).toContain("上一页");
    expect(source).toContain("下一页");
    expect(source).toContain("上一组");
    expect(source).toContain("下一组");
    expect(source).toContain("detail-section--context");
    expect(source).toContain("detail-section__context-body");
    expect(source).toContain("detail-section__context-pager");
    expect(source).toContain("detail-context__item--paged");
    expect(source).toContain("grid-auto-rows: 1fr;");
    expect(source).toContain("height: 560px;");
    expect(source).toContain("grid-template-rows: auto minmax(0, 1fr) auto;");
    expect(source).toContain("min-height: 176px;");
    expect(source).toContain("max-height: 176px;");
    expect(source).toContain("overflow: hidden;");
  });

  it("复核工作区操作按钮使用高对比专用样式", () => {
    const source = readRecordDetailSource();

    expect(source).toContain("detail-action-button");
    expect(source).toContain("detail-action-button--ai");
    expect(source).toContain("detail-action-button--cloud");
    expect(source).toContain("detail-action-button--board");
    expect(source).toContain("detail-action-button--refresh");
    expect(source).toContain("background: #38bdf8");
    expect(source).toContain("background: #f97316");
    expect(source).toContain("background: #facc15");
  });
});
