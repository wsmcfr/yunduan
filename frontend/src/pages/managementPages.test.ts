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
});
