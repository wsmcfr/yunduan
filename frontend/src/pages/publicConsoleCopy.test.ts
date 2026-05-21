import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * 读取页面单文件组件源码。
 *
 * 主要流程：
 * 1. 基于 frontend 工作目录解析页面路径；
 * 2. 读取 Vue SFC 原始文本；
 * 3. 交给轻量源码契约测试断言关键文案和布局约束。
 *
 * @param relativePath 页面文件相对 frontend 目录的路径。
 * @returns 页面源码文本。
 */
function readPageSource(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

describe("public console copy and login layout contracts", () => {
  it("仪表盘标题使用后台运营语义，不再使用比赛项目表达", () => {
    /**
     * 仪表盘是管理员进入系统后的工作台。
     * 这里锁住标题和说明，避免页面又退回到竞赛展示页或占位说明的语气。
     */
    const source = readPageSource("src/pages/DashboardPage.vue");

    expect(source).toContain('title="运营态势总览"');
    expect(source).toContain("检测规模、风险热点、审核闭环和图库覆盖");
    expect(source).not.toContain("比赛项目总览");
    expect(source).not.toContain("首页不再只放几个占位表格");
  });

  it("登录页左右主面板在桌面端等宽等高并铺满首屏", () => {
    /**
     * 登录页桌面版应像一个左右均分的入口工作台。
     * 左右卡片大小不一致会让认证中心像补丁面板，因此用源码契约锁住等分网格和撑满高度。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(source).toContain("min-height: calc(100dvh - 56px);");
    expect(source).toContain("height: calc(100dvh - 56px);");
    expect(source).toContain("justify-self: stretch;");
    expect(source).not.toContain("grid-template-columns: minmax(0, 1fr) minmax(380px, 560px);");
    expect(source).not.toContain("width: min(100%, 560px);");
  });

  it("登录页左侧介绍聚焦工业缺陷检测控制台能力", () => {
    /**
     * 公共认证页不能像赛事宣传页，也不应把技术安全细节作为主卖点。
     * 左侧区域应说明用户登录后能管理什么、追踪什么、处理什么。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("工业缺陷检测云端控制台");
    expect(source).toContain("云端检测系统");
    expect(source).toContain("检测记录、样本图库、设备状态、零件台账与统计分析");
    expect(source).toContain("人工复核与 AI 辅助研判");
    expect(source).toContain("统一检测入口");
    expect(source).toContain("审核闭环");
    expect(source).toContain("数据留痕");
    expect(source).not.toContain("第九届嵌入式芯片与系统设计竞赛");
    expect(source).not.toContain("双注册路径");
    expect(source).not.toContain("密码加固");
  });

  it("登录页主标题降级为控制台入口标题，不再使用超大展示字", () => {
    /**
     * 左侧主标题是入口工作台标题，不是营销海报标题。
     * 字号上限要收敛，避免在宽屏下把“云端检测系统”拆成大块空白字面。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("<h1 class=\"login-page__title\">云端检测系统</h1>");
    expect(source).toMatch(
      /\.login-page__title\s*\{[\s\S]*font-size:\s*clamp\(32px,\s*3\.2vw,\s*48px\);/,
    );
    expect(source).not.toContain("font-size: clamp(50px, 5.5vw, 78px);");
  });

  it("登录和注册入口在宽面板内横向铺开，避免表单区出现空框", () => {
    /**
     * 右侧认证卡宽度接近半屏，登录字段和注册模式不能只挤在左侧。
     * 登录表单应使用两列字段，注册模式切换应铺满整行。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("login-page__login-grid");
    expect(source).toMatch(
      /\.login-page__login-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/,
    );
    expect(source).toMatch(
      /\.login-page__login-submit\s*\{[\s\S]*grid-column:\s*1 \/ -1;/,
    );
    expect(source).toMatch(
      /\.login-page__mode-switch\s*:deep\(\.el-radio-group\)\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/,
    );
    expect(source).toContain("login-page__signin-context");
    expect(source).toContain("登录后处理重点");
    expect(source).toContain("默认入口");
    expect(source).toContain("待复核记录");
    expect(source).toContain("已有公司成员，拿到邀请码后直接绑定公司。");
  });

  it("登录页用业务信息块填充左右面板空白", () => {
    /**
     * 登录页两个主面板已经被拉到同高，不能只靠背景装饰撑满。
     * 左侧补检测流程和平台覆盖范围，右侧补登录后的工作区预览，让空白都承载业务信息。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("login-page__process-strip");
    expect(source).toContain("现场采集");
    expect(source).toContain("云端归档");
    expect(source).toContain("复核判定");
    expect(source).toContain("统计追溯");
    expect(source).toContain("平台覆盖范围");
    expect(source).toContain("login-page__coverage-grid");
    expect(source).toContain("检测记录");
    expect(source).toContain("系统设置");
    expect(source).toContain("登录后工作区预览");
    expect(source).toContain("login-page__workspace-preview");
    expect(source).toContain("仪表盘");
    expect(source).toContain("样本图库");
  });

  it("登录页左侧流程区不再叠加额外装饰边框", () => {
    /**
     * 左侧顶部流程卡自身已经有边框。
     * 右上角额外伪元素边框会在第四张流程卡后面形成误读为布局错误的背景框。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).not.toContain(".login-page__hero::before");
    expect(source).toContain(".login-page__hero::after");
  });

  it("登录页左侧能力卡使用可扫读清单填充卡内空白", () => {
    /**
     * 左侧底部三张能力卡在不同桌面高度下会承担补足空间的职责。
     * 卡片内部必须有具体工作项，而不是只显示一行介绍后留下大块空白。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("LOGIN_HIGHLIGHT_ITEMS");
    expect(source).toContain("login-page__highlight-list");
    expect(source).toContain("记录筛选");
    expect(source).toContain("AI 建议");
    expect(source).toContain("设备维度");
  });

  it("登录页不再用弹性空行制造主面板留白", () => {
    /**
     * 左右主面板等高后，空白必须由具体信息模块填充。
     * 这里锁住布局：不能再用 1fr 空行把内容贴到上下两端。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("运行快照");
    expect(source).toContain("账号路径说明");
    expect(source).toContain("login-page__snapshot-grid");
    expect(source).toContain("login-page__auth-paths");
    expect(source).not.toContain("grid-template-rows: auto auto auto auto minmax(0, 1fr) auto;");
    expect(source).not.toContain("grid-template-rows: auto minmax(0, auto) minmax(0, 1fr);");
  });

  it("登录页右侧用工作区预览吸收高屏剩余空间", () => {
    /**
     * 桌面高屏下，右侧表单内容比左侧更短，底部容易露出大块空白。
     * 这里要求认证卡用纵向流式布局，避免 Element Plus 标签页高度被压缩后和下方信息块重叠。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toMatch(
      /\.login-page__form-card\s*\{[\s\S]*display:\s*flex;[\s\S]*flex-direction:\s*column;/,
    );
    expect(source).toMatch(
      /\.login-page__tabs\s*:deep\(\.el-tabs__content\)\s*\{[\s\S]*overflow:\s*visible;/,
    );
    expect(source).toMatch(
      /\.login-page__workspace-preview\s*\{[\s\S]*flex:\s*1 0 auto;/,
    );
  });

  it("登录页矮屏桌面会压缩左侧信息密度避免底部裁切", () => {
    /**
     * 1280x720 一类桌面视口仍应保持左右两栏，但左侧标题、流程和辅助卡片必须收紧。
     * 如果没有矮屏专用规则，底部能力卡会被左侧面板裁掉。
     */
    const source = readPageSource("src/pages/LoginPage.vue");

    expect(source).toContain("@media (max-width: 1360px) and (max-height: 760px)");
    expect(source).toMatch(
      /@media \(max-width: 1360px\) and \(max-height: 760px\)[\s\S]*\.login-page__title\s*\{[\s\S]*font-size:\s*40px;/,
    );
    expect(source).toMatch(
      /@media \(max-width: 1360px\) and \(max-height: 760px\)[\s\S]*\.login-page__snapshot-item small\s*\{[\s\S]*display:\s*none;/,
    );
  });
});
