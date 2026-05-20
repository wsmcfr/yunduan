import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * 读取布局组件源码。
 *
 * 主要流程：
 * 1. 基于 frontend 工作目录解析组件路径；
 * 2. 读取单文件组件源码文本；
 * 3. 让布局契约测试验证关键 CSS 和模板约束。
 *
 * @param relativePath 布局组件相对 frontend 目录的路径。
 * @returns 布局组件源码文本。
 */
function readLayoutSource(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

describe("authenticated shell responsive layout contracts", () => {
  it("小屏外壳保留一页视口并给业务面板分配真实高度", () => {
    /**
     * 这个用例保护一页控制台交互：
     * 小屏下 shell 不能被侧栏和顶部栏挤到只剩 0px 或几十像素，业务滚动仍应交给 .page-grid。
     */
    const source = readLayoutSource("src/components/layout/AppShell.vue");

    expect(source).toContain("grid-template-rows: auto minmax(0, 1fr);");
    expect(source).toContain("max-height: calc(100dvh -");
    expect(source).toContain("overflow-y: auto;");
  });

  it("侧栏在小屏使用紧凑导航并隐藏开发环境卡片", () => {
    /**
     * 这个用例保护比赛演示观感：
     * 导航可以保留在同一屏，但不能完整占据上半屏，也不能显示开发环境说明卡片。
     */
    const source = readLayoutSource("src/components/layout/AppSidebar.vue");

    expect(source).toContain(".sidebar--compact");
    expect(source).not.toContain("runtimeEnvironmentLabel");
    expect(source).not.toContain("sidebar__footer app-panel");
  });
});
