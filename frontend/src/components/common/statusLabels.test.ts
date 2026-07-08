import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * 读取前端源码文件内容。
 *
 * 主要流程：
 * 1. 以 frontend 工作目录作为基准解析相对路径；
 * 2. 读取源码文本；
 * 3. 交给状态文案契约测试断言关键标签不会漂移。
 *
 * @param relativePath 前端目录下的相对路径。
 * @returns 指定源码文件的完整文本内容。
 */
function readSource(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

describe("detection result labels", () => {
  it("MP 初检 uncertain 结果在选项和状态标签中都显示为待复核", () => {
    /**
     * MP157 上报的 `uncertain` 表示设备无法明确分拣，需要进入待复核盒。
     * 这里锁住公共选项和通用状态标签，避免列表筛选与红框里的 MP 初检列文案不一致。
     */
    const optionsSource = readSource("src/constants/options.ts");
    const statusTagSource = readSource("src/components/common/StatusTag.vue");

    expect(optionsSource).toContain('{ label: "待复核", value: "uncertain" }');
    expect(statusTagSource).toContain('uncertain: "待复核"');
  });
});
