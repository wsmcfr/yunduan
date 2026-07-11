import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * 读取页面单文件组件源码。
 *
 * 主要流程：
 * 1. 从当前 frontend 工作目录解析页面路径；
 * 2. 读取 SFC 文本；
 * 3. 交给页面契约测试做轻量断言。
 *
 * @param relativePath 页面文件相对 frontend 目录的路径。
 * @returns 页面源码文本。
 */
function readPageSource(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

describe("management page pagination and resource refresh contracts", () => {
  it.each([
    ["设备管理页", "src/pages/DevicesPage.vue"],
    ["零件管理页", "src/pages/PartsPage.vue"],
  ])("%s exposes page-size selection and resets to the first page", (_name, path) => {
    const source = readPageSource(path);

    expect(source).toContain('layout="sizes, prev, pager, next, total"');
    expect(source).toContain(':page-sizes="[10, 20, 50, 100]"');
    expect(source).toContain('@size-change="handlePageSizeChange"');
    expect(source).toContain("async function handlePageSizeChange(nextPageSize: number): Promise<void>");
    expect(source).toContain("pageSize.value = nextPageSize;");
    expect(source).toContain("currentPage.value = 1;");
  });

  it("检测记录页删除后刷新列表和分类入口资源", () => {
    const source = readPageSource("src/pages/RecordsPage.vue");

    expect(source).toContain("async function refreshRecordsView(): Promise<void>");
    expect(source).toContain("await Promise.all([loadOptions(), refresh()]);");
    expect(source).toContain("await refreshRecordsView();");
  });

  it("零件管理页明确区分零件大类和具体类型", () => {
    const source = readPageSource("src/pages/PartsPage.vue");

    expect(source).toContain("零件大类入口");
    expect(source).toContain("具体零件类型明细");
    expect(source).toContain("resolvePartDisplayName");
  });

  it.each([
    ["设备管理页", "src/pages/DevicesPage.vue"],
    ["检测记录页", "src/pages/RecordsPage.vue"],
  ])("%s 的操作列不使用右固定层", (_name, path) => {
    /**
     * 这个断言保护窄屏表格体验：
     * Element Plus 的右固定列会生成独立 fixed 区域，在内部滚动面板和暗色主题下容易形成割裂灰块。
     */
    const source = readPageSource(path);

    expect(source).not.toContain('fixed="right"');
  });

  it.each([
    ["设备管理页", "src/pages/DevicesPage.vue"],
    ["零件管理页", "src/pages/PartsPage.vue"],
    ["检测记录页", "src/pages/RecordsPage.vue"],
    ["系统设置页", "src/pages/SettingsPage.vue"],
  ])("%s 的操作列使用紧凑横向按钮组", (_name, path) => {
    /**
     * 操作列是管理表格最容易显得拥挤的位置。
     * 这里用源码契约锁住桌面端横向按钮组，避免“编辑/删除/停用/复核/详情”重新变成竖向堆叠。
     */
    const source = readPageSource(path);

    expect(source).toContain("table-action-button");
    expect(source).toContain("flex-wrap: nowrap;");
    expect(source).toContain(".table-actions :deep(.el-button + .el-button)");
  });

  it("AI 网关模型操作列保持一行紧凑按钮", () => {
    /**
     * AI 网关模型表一行有“编辑 / 停用 / 删除”三个短动作。
     * 这里锁住列宽和统一按钮类，避免按钮被窄列挤成两行，形成截图里的竖向堆叠问题。
     */
    const source = readPageSource("src/pages/SettingsPage.vue");

    expect(source).toContain('<ElTableColumn label="操作" min-width="204" align="center"');
    expect(source).toContain('class="table-action-button" text type="primary"');
    expect(source).toContain('class="table-action-button" text type="danger"');
  });

  it("检测详情页展示 MP157 中文解释并保留原始上下文入口", () => {
    /**
     * 详情页不能只把原始 JSON 压平成工程字段；中文解释用于现场阅读，原始上下文只保留给排障。
     */
    const source = readPageSource("src/pages/RecordDetailPage.vue");

    expect(source).toContain("MP157 中文解释");
    expect(source).toContain("contextExplanations");
    expect(source).toContain("原始上下文");
  });

  it("检测详情页的 MP157 中文解释在固定框内分页展示", () => {
    /**
     * MP157 解释项可能一次上报几十个字段。
     * 详情页必须把每个解释分组限制在固定内容框内，通过分页切换条目，避免长字段把卡片撑到互相重叠。
     */
    const source = readPageSource("src/pages/RecordDetailPage.vue");

    expect(source).toContain("CONTEXT_EXPLANATION_PAGE_SIZE");
    expect(source).toContain("contextExplanationPageByGroup");
    expect(source).toContain("paginatedContextExplanationGroups");
    expect(source).toContain("handleContextExplanationPageChange");
    expect(source).toContain('class="detail-context-explanations__frame"');
    expect(source).toContain('<ElPagination');
    expect(source).toContain('@current-change="(page) => handleContextExplanationPageChange(group.key, page)"');
    expect(source).toContain('class="detail-context-explanations__value"');
    expect(source).toContain("height: clamp(420px, 44dvh, 560px);");
    expect(source).toContain("overflow-y: auto;");
  });
});
