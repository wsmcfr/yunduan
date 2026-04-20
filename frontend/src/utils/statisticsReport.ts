import type {
  DeviceQualityItem,
  PartQualityItem,
  StatisticsAIAnalysisResponse,
  StatisticsOverview,
} from "@/types/models";
import { formatDateTime } from "@/utils/format";
import {
  buildTrendAreaPath,
  buildTrendAxisTicks,
  buildTrendSeriesPoints,
  buildTrendSmoothPath,
  buildTrendValueTicks,
} from "@/utils/trendChart";

export interface StatisticsReportPayload {
  overview: StatisticsOverview;
  aiAnalysis: StatisticsAIAnalysisResponse | null;
  partLabel?: string | null;
  deviceLabel?: string | null;
}

const SVG_WIDTH = 1400;
const SVG_HEIGHT = 1760;

/**
 * 转义 SVG/HTML 中的特殊字符，避免备注、缺陷名和 AI 分析文本破坏导出内容结构。
 */
function escapeMarkup(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * 把数值转成百分比文本，统一导出报告与页面文案的口径。
 */
function formatPercent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
}

/**
 * 构造当前统计窗口的范围说明，便于导出图片和 PDF 时保留筛选上下文。
 */
function buildScopeSummary(payload: StatisticsReportPayload): string {
  const { filters } = payload.overview;
  const scopeParts = [
    `时间范围：${filters.startDate ?? "未限定"} 至 ${filters.endDate ?? "未限定"}`,
    `窗口天数：${filters.days} 天`,
  ];

  if (payload.partLabel) {
    scopeParts.push(`零件：${payload.partLabel}`);
  }
  if (payload.deviceLabel) {
    scopeParts.push(`设备：${payload.deviceLabel}`);
  }

  return scopeParts.join(" | ");
}

/**
 * 把一段长文本按指定长度切成多行，供 SVG 文本框和打印页正文复用。
 */
function wrapText(value: string, maxCharsPerLine: number): string[] {
  const normalizedValue = value.replace(/\r/g, "").trim();
  if (!normalizedValue) {
    return [];
  }

  const wrappedLines: string[] = [];
  for (const rawLine of normalizedValue.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      wrappedLines.push("");
      continue;
    }

    let startIndex = 0;
    while (startIndex < line.length) {
      wrappedLines.push(line.slice(startIndex, startIndex + maxCharsPerLine));
      startIndex += maxCharsPerLine;
    }
  }

  return wrappedLines;
}

/**
 * 生成 SVG 内部的多行文本片段。
 */
function buildSvgTextBlock(lines: string[], x: number, lineHeight: number): string {
  return lines
    .map((line, index) => {
      const offset = index === 0 ? 0 : lineHeight;
      return `<tspan x="${x}" dy="${offset}">${escapeMarkup(line || " ")}</tspan>`;
    })
    .join("");
}

/**
 * 生成排行条形图行，供零件排行和设备排行复用。
 */
function buildRankingRows<TItem extends PartQualityItem | DeviceQualityItem>(
  items: TItem[],
  options: {
    labelResolver: (item: TItem) => string;
  },
): string {
  const maxCount = Math.max(...items.map((item) => item.badCount + item.uncertainCount), 1);

  return items
    .map((item, index) => {
      const riskCount = item.badCount + item.uncertainCount;
      const barWidth = (riskCount / maxCount) * 320;
      const rowY = 0 + index * 62;
      const label = options.labelResolver(item);
      return `
        <g transform="translate(0 ${rowY})">
          <text x="0" y="18" fill="#f3f7fb" font-size="16" font-weight="700">${escapeMarkup(label)}</text>
          <text x="0" y="40" fill="#96a9bf" font-size="13">总量 ${item.totalCount} | 不良 ${item.badCount} | 待确认 ${item.uncertainCount} | 良率 ${formatPercent(item.passRate)}</text>
          <rect x="0" y="48" width="320" height="8" rx="4" fill="#18324b" />
          <rect x="0" y="48" width="${barWidth.toFixed(1)}" height="8" rx="4" fill="#ff7a6d" />
        </g>
      `;
    })
    .join("");
}

/**
 * 构造统计摘要卡片。
 */
function buildSummaryCards(payload: StatisticsReportPayload): string {
  const { summary } = payload.overview;
  const cardItems = [
    {
      title: "总检测量",
      value: `${summary.totalCount}`,
      hint: "当前筛选窗口内的全部记录数",
      accent: "#7fe4d0",
    },
    {
      title: "当前良率",
      value: formatPercent(summary.passRate),
      hint: `良品 ${summary.goodCount} / 不良 ${summary.badCount}`,
      accent: "#4ad49a",
    },
    {
      title: "待确认",
      value: `${summary.uncertainCount}`,
      hint: "仍需结合复核或补证据确认",
      accent: "#ffcc62",
    },
    {
      title: "待审核",
      value: `${summary.pendingReviewCount}`,
      hint: `已审核 ${summary.reviewedCount} 条`,
      accent: "#6aa7ff",
    },
  ];

  return cardItems
    .map((item, index) => {
      const x = 60 + index * 325;
      return `
        <g transform="translate(${x} 150)">
          <rect width="285" height="140" rx="22" fill="#112740" stroke="#213a54" />
          <rect width="285" height="6" rx="3" fill="${item.accent}" />
          <text x="24" y="46" fill="#96a9bf" font-size="16" letter-spacing="1">${escapeMarkup(item.title)}</text>
          <text x="24" y="92" fill="#f8fbff" font-size="42" font-weight="700">${escapeMarkup(item.value)}</text>
          <text x="24" y="122" fill="#8ea4bd" font-size="14">${escapeMarkup(item.hint)}</text>
        </g>
      `;
    })
    .join("");
}

/**
 * 构造缺陷分布条形图。
 */
function buildDefectRows(payload: StatisticsReportPayload): string {
  const topItems = payload.overview.defectDistribution.slice(0, 6);
  const maxCount = Math.max(...topItems.map((item) => item.count), 1);

  return topItems
    .map((item, index) => {
      const rowY = 0 + index * 52;
      const barWidth = (item.count / maxCount) * 360;
      return `
        <g transform="translate(0 ${rowY})">
          <text x="0" y="18" fill="#f3f7fb" font-size="15" font-weight="700">${escapeMarkup(item.defectType)}</text>
          <text x="360" y="18" fill="#7fe4d0" font-size="15" text-anchor="end">${item.count}</text>
          <rect x="0" y="28" width="360" height="10" rx="5" fill="#18324b" />
          <rect x="0" y="28" width="${barWidth.toFixed(1)}" height="10" rx="5" fill="#7fe4d0" />
        </g>
      `;
    })
    .join("");
}

/**
 * 生成统计导出所需的 SVG 文本。
 */
export function buildStatisticsReportSvg(payload: StatisticsReportPayload): string {
  const { overview, aiAnalysis } = payload;
  /**
   * 导出图表沿用页面相同的横轴抽稀策略，避免页面与 PNG/PDF 展示口径不一致。
   */
  const axisTicks = buildTrendAxisTicks(overview.dailyTrend);
  const trendRect = {
    x: 0,
    y: 0,
    width: 460,
    height: 180,
  };
  const rawTrendMaxValue = Math.max(
    ...overview.dailyTrend.flatMap((item) => [item.totalCount, item.badCount, item.uncertainCount]),
    1,
  );
  const valueTicks = buildTrendValueTicks(rawTrendMaxValue);
  const trendMaxValue = valueTicks[valueTicks.length - 1]?.value ?? rawTrendMaxValue;
  const totalSeries = buildTrendSeriesPoints(
    overview.dailyTrend.map((item) => item.totalCount),
    trendRect,
    { maxValue: trendMaxValue },
  );
  const badSeries = buildTrendSeriesPoints(
    overview.dailyTrend.map((item) => item.badCount),
    trendRect,
    { maxValue: trendMaxValue },
  );
  const uncertainSeries = buildTrendSeriesPoints(
    overview.dailyTrend.map((item) => item.uncertainCount),
    trendRect,
    { maxValue: trendMaxValue },
  );
  const findings = overview.keyFindings.slice(0, 5);
  const aiLines = wrapText(
    aiAnalysis?.answer ?? "尚未生成 AI 批次分析，可先在统计页选择模型后发起分析。",
    34,
  ).slice(0, 16);

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${SVG_WIDTH}" height="${SVG_HEIGHT}" viewBox="0 0 ${SVG_WIDTH} ${SVG_HEIGHT}">
  <defs>
    <linearGradient id="reportBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#091525" />
      <stop offset="48%" stop-color="#0d1c30" />
      <stop offset="100%" stop-color="#10253c" />
    </linearGradient>
    <linearGradient id="panelStroke" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#28445e" />
      <stop offset="100%" stop-color="#1a324a" />
    </linearGradient>
  </defs>

  <rect width="${SVG_WIDTH}" height="${SVG_HEIGHT}" fill="url(#reportBg)" />
  <circle cx="150" cy="120" r="180" fill="#1fae9b" opacity="0.12" />
  <circle cx="1240" cy="1600" r="260" fill="#4f9fff" opacity="0.1" />

  <text x="60" y="72" fill="#7fe4d0" font-size="18" font-weight="700" letter-spacing="2">STATISTICS REPORT</text>
  <text x="60" y="112" fill="#f8fbff" font-size="40" font-weight="700">产品批次统计分析</text>
  <text x="60" y="138" fill="#8ea4bd" font-size="16">${escapeMarkup(buildScopeSummary(payload))}</text>
  <text x="60" y="164" fill="#8ea4bd" font-size="14">生成时间：${escapeMarkup(formatDateTime(overview.generatedAt))}</text>

  ${buildSummaryCards(payload)}

  <g transform="translate(60 340)">
    <rect width="620" height="360" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">趋势曲线</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">总量 / 不良 / 待确认按天变化</text>
    <g transform="translate(82 110)">
      <defs>
        <linearGradient id="reportTrendArea" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#7fe4d0" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#7fe4d0" stop-opacity="0.03" />
        </linearGradient>
      </defs>
      <line x1="0" y1="180" x2="460" y2="180" stroke="#28445e" />
      <line x1="0" y1="0" x2="0" y2="180" stroke="#28445e" />
      ${valueTicks
        .map((item) => {
          const y = (180 - 180 * item.ratio).toFixed(1);
          return `
            <line x1="0" y1="${y}" x2="460" y2="${y}" stroke="#20384f" stroke-dasharray="6 6" />
            <text x="-12" y="${Number(y) + 4}" fill="#7d95af" font-size="11" text-anchor="end">${escapeMarkup(item.label)}</text>
          `;
        })
        .join("")}
      <path fill="url(#reportTrendArea)" stroke="none" d="${buildTrendAreaPath(totalSeries, 180)}" />
      <path fill="none" stroke="#7fe4d0" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="${buildTrendSmoothPath(totalSeries)}" />
      <path fill="none" stroke="#ff7a6d" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="${buildTrendSmoothPath(badSeries)}" />
      <path fill="none" stroke="#ffcc62" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="${buildTrendSmoothPath(uncertainSeries)}" />
      ${[totalSeries, badSeries, uncertainSeries]
        .map((seriesPoints, seriesIndex) => {
          const color = seriesIndex === 0 ? "#7fe4d0" : seriesIndex === 1 ? "#ff7a6d" : "#ffcc62";
          return seriesPoints
            .map(
              (point) => `<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3.2" fill="${color}" stroke="#112740" stroke-width="1.2" />`,
            )
            .join("");
        })
        .join("")}
      ${axisTicks
        .map((item) => {
          const point = totalSeries[item.index] ?? totalSeries[0];
          return `<text x="${point.x.toFixed(1)}" y="206" fill="#7d95af" font-size="11" text-anchor="middle">${escapeMarkup(item.label)}</text>`;
        })
        .join("")}
    </g>
    <g transform="translate(28 302)">
      <circle cx="12" cy="0" r="6" fill="#7fe4d0" />
      <text x="28" y="4" fill="#d8e4f2" font-size="13">总量</text>
      <circle cx="112" cy="0" r="6" fill="#ff7a6d" />
      <text x="128" y="4" fill="#d8e4f2" font-size="13">不良</text>
      <circle cx="212" cy="0" r="6" fill="#ffcc62" />
      <text x="228" y="4" fill="#d8e4f2" font-size="13">待确认</text>
    </g>
  </g>

  <g transform="translate(720 340)">
    <rect width="620" height="360" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">缺陷与结论分布</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">重点缺陷聚集度和当前结果结构</text>
    <g transform="translate(28 112)">
      ${buildDefectRows(payload)}
    </g>
    <g transform="translate(430 118)">
      <text x="0" y="0" fill="#8ea4bd" font-size="14">结果结构</text>
      ${overview.resultDistribution
        .map((item, index) => {
          const itemY = 34 + index * 54;
          const color =
            item.result === "good" ? "#4ad49a" : item.result === "bad" ? "#ff7a6d" : "#ffcc62";
          const label =
            item.result === "good" ? "良品" : item.result === "bad" ? "不良" : "待确认";
          const barWidth = overview.summary.totalCount === 0
            ? 0
            : (item.count / overview.summary.totalCount) * 130;
          return `
            <g transform="translate(0 ${itemY})">
              <text x="0" y="0" fill="#dbe7f3" font-size="15">${label}</text>
              <text x="140" y="0" fill="${color}" font-size="15" text-anchor="end">${item.count}</text>
              <rect x="0" y="12" width="140" height="8" rx="4" fill="#18324b" />
              <rect x="0" y="12" width="${barWidth.toFixed(1)}" height="8" rx="4" fill="${color}" />
            </g>
          `;
        })
        .join("")}
      <text x="0" y="214" fill="#8ea4bd" font-size="14">审核状态</text>
      ${overview.reviewStatusDistribution
        .map((item, index) => {
          const itemY = 248 + index * 42;
          const color =
            item.reviewStatus === "reviewed"
              ? "#4ad49a"
              : item.reviewStatus === "ai_reserved"
                ? "#6aa7ff"
                : "#ffcc62";
          const label =
            item.reviewStatus === "reviewed"
              ? "已审核"
              : item.reviewStatus === "ai_reserved"
                ? "AI 预留"
                : "待审核";
          return `
            <g transform="translate(0 ${itemY})">
              <circle cx="6" cy="-4" r="6" fill="${color}" />
              <text x="22" y="0" fill="#dbe7f3" font-size="14">${label}</text>
              <text x="140" y="0" fill="#96a9bf" font-size="14" text-anchor="end">${item.count}</text>
            </g>
          `;
        })
        .join("")}
    </g>
  </g>

  <g transform="translate(60 740)">
    <rect width="620" height="400" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">零件风险排行</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">按不良与待确认规模排序，优先暴露质量压力更高的零件</text>
    <g transform="translate(28 116)">
      ${buildRankingRows(overview.partQualityRanking.slice(0, 5), {
        labelResolver: (item) => `${item.partName} / ${item.partCode}`,
      })}
    </g>
  </g>

  <g transform="translate(720 740)">
    <rect width="620" height="400" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">设备风险排行</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">用于定位异常可能更偏向设备侧还是产品侧</text>
    <g transform="translate(28 116)">
      ${buildRankingRows(overview.deviceQualityRanking.slice(0, 5), {
        labelResolver: (item) => `${item.deviceName} / ${item.deviceCode}`,
      })}
    </g>
  </g>

  <g transform="translate(60 1180)">
    <rect width="500" height="500" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">关键发现</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">系统根据统计结果自动提炼出的重点观察点</text>
    ${findings
      .map((finding, index) => {
        const y = 120 + index * 82;
        return `
          <g transform="translate(28 ${y})">
            <circle cx="8" cy="-8" r="8" fill="#7fe4d0" />
            <text x="26" y="0" fill="#dbe7f3" font-size="15">
              ${buildSvgTextBlock(wrapText(finding, 28).slice(0, 3), 26, 22)}
            </text>
          </g>
        `;
      })
      .join("")}
  </g>

  <g transform="translate(590 1180)">
    <rect width="750" height="500" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">AI 批次分析</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">${escapeMarkup(aiAnalysis?.providerHint ?? "未选择模型")}</text>
    <text x="28" y="98" fill="#8ea4bd" font-size="13">分析时间：${escapeMarkup(aiAnalysis ? formatDateTime(aiAnalysis.generatedAt) : "未生成")}</text>
    <text x="28" y="138" fill="#dbe7f3" font-size="16">
      ${buildSvgTextBlock(aiLines, 28, 24)}
    </text>
  </g>
</svg>`;
}

/**
 * 统一下载 Blob，避免图片导出和其他下载流程重复写锚点逻辑。
 */
function downloadBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

/**
 * 把统计报告导出为 PNG 图片。
 */
export async function exportStatisticsReportPng(payload: StatisticsReportPayload): Promise<void> {
  const svgText = buildStatisticsReportSvg(payload);
  const svgBlob = new Blob([svgText], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const nextImage = new Image();
      nextImage.onload = () => resolve(nextImage);
      nextImage.onerror = () => reject(new Error("统计报告 SVG 渲染失败"));
      nextImage.src = svgUrl;
    });

    const canvas = document.createElement("canvas");
    const scale = Math.max(window.devicePixelRatio || 1, 2);
    canvas.width = SVG_WIDTH * scale;
    canvas.height = SVG_HEIGHT * scale;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("浏览器当前无法创建图片导出画布");
    }

    context.scale(scale, scale);
    context.drawImage(image, 0, 0, SVG_WIDTH, SVG_HEIGHT);

    const pngBlob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error("统计报告 PNG 导出失败"));
          return;
        }
        resolve(blob);
      }, "image/png");
    });

    downloadBlob(pngBlob, `statistics-report-${Date.now()}.png`);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}

/**
 * 生成打印用 HTML，让浏览器直接走“另存为 PDF”流程。
 */
function buildStatisticsReportHtml(payload: StatisticsReportPayload): string {
  const svgMarkup = buildStatisticsReportSvg(payload).replace(/^<\?xml[^>]*>\s*/, "");
  const aiAnswer = escapeMarkup(payload.aiAnalysis?.answer ?? "尚未生成 AI 批次分析。");
  const keyFindingItems = payload.overview.keyFindings
    .map((item) => `<li>${escapeMarkup(item)}</li>`)
    .join("");

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>统计分析报告</title>
    <style>
      body {
        margin: 0;
        padding: 24px;
        color: #10233a;
        background: #f4f7fb;
        font-family: "Bahnschrift", "PingFang SC", "Microsoft YaHei", sans-serif;
      }
      .report-shell {
        max-width: 1200px;
        margin: 0 auto;
        display: grid;
        gap: 20px;
      }
      .panel {
        background: #ffffff;
        border: 1px solid #d8e3ef;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 10px 30px rgba(22, 40, 67, 0.08);
      }
      .report-svg {
        width: 100%;
        height: auto;
        display: block;
      }
      .meta {
        color: #5a7089;
        line-height: 1.8;
      }
      h1, h2, p {
        margin: 0;
      }
      h2 {
        margin-bottom: 12px;
      }
      .ai-text {
        white-space: pre-wrap;
        line-height: 1.8;
      }
      .report-svg,
      .panel svg {
        width: 100%;
        height: auto;
        display: block;
      }
      @media print {
        body {
          padding: 0;
          background: #ffffff;
        }
        .panel {
          box-shadow: none;
          break-inside: avoid;
        }
      }
    </style>
  </head>
  <body>
    <div class="report-shell">
      <section class="panel">
        ${svgMarkup}
      </section>
      <section class="panel">
        <h2>导出说明</h2>
        <p class="meta">${escapeMarkup(buildScopeSummary(payload))}</p>
        <p class="meta">报告生成时间：${escapeMarkup(formatDateTime(payload.overview.generatedAt))}</p>
      </section>
      <section class="panel">
        <h2>关键发现明细</h2>
        <ul>${keyFindingItems}</ul>
      </section>
      <section class="panel">
        <h2>AI 批次分析全文</h2>
        <div class="meta">模型：${escapeMarkup(payload.aiAnalysis?.providerHint ?? "未生成")}</div>
        <div class="meta">分析时间：${escapeMarkup(payload.aiAnalysis ? formatDateTime(payload.aiAnalysis.generatedAt) : "未生成")}</div>
        <div class="ai-text">${aiAnswer}</div>
      </section>
    </div>
    <script>
      window.addEventListener("load", () => {
        window.setTimeout(() => {
          window.print();
        }, 350);
      });
    </script>
  </body>
</html>`;
}

/**
 * 打开浏览器打印窗口，用户可以直接选择“另存为 PDF”。
 */
export function openStatisticsReportPrintWindow(payload: StatisticsReportPayload): boolean {
  /**
   * 这里不再使用 `about:blank + document.write + noopener` 的组合。
   * 部分浏览器会在这种组合下直接保留一页空白 about:blank，导致用户看到白屏。
   * 改为先生成完整 HTML Blob，再通过 Blob URL 打开，可以稳定兼容本地与服务器部署。
   */
  const htmlBlob = new Blob([buildStatisticsReportHtml(payload)], {
    type: "text/html;charset=utf-8",
  });
  const htmlUrl = URL.createObjectURL(htmlBlob);
  const printWindow = window.open(htmlUrl, "_blank");
  if (!printWindow) {
    URL.revokeObjectURL(htmlUrl);
    return false;
  }

  /**
   * 给新窗口一点时间完成资源解析后再释放 Blob URL，避免页面还没读完就被提前回收。
   */
  window.setTimeout(() => {
    URL.revokeObjectURL(htmlUrl);
  }, 60_000);
  return true;
}
