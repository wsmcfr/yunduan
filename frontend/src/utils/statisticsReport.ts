import type {
  AIChatMessage,
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
  aiConversation?: AIChatMessage[];
  partLabel?: string | null;
  deviceLabel?: string | null;
}

interface StatisticsReportSvgDocument {
  svgText: string;
  width: number;
  height: number;
}

interface NormalizedConversationMessage {
  role: AIChatMessage["role"];
  content: string;
  createdAt: string | null;
}

interface ConversationSvgBlock {
  role: AIChatMessage["role"];
  headerText: string;
  contentLines: string[];
  height: number;
}

const SVG_WIDTH = 1400;
const BASE_BOTTOM_SECTION_Y = 1180;
const MIN_FINDINGS_PANEL_HEIGHT = 500;
const MIN_AI_PANEL_HEIGHT = 500;
const SVG_BOTTOM_MARGIN = 80;
const POSTER_WIDTH = 1600;
const POSTER_HEIGHT = 1880;

/**
 * 转义 SVG/HTML 中的特殊字符，避免备注、缺陷名和 AI 文本破坏导出结构。
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
 * 把数值转换成百分比文本，统一导出报告与页面展示口径。
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
 * 把一段长文本按指定长度切成多行，供 SVG 文本块和打印页正文复用。
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
 * 把一组文本行裁剪到固定行数，并在最后补省略号。
 * 海报图需要固定高度，因此不能继续像完整长图那样无限增高。
 */
function clampLines(lines: string[], maxLines: number): string[] {
  if (lines.length <= maxLines) {
    return lines;
  }

  const nextLines = lines.slice(0, maxLines);
  const lastLine = nextLines[maxLines - 1] ?? "";
  nextLines[maxLines - 1] = `${lastLine.slice(0, Math.max(lastLine.length - 1, 0))}…`;
  return nextLines;
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
 * 统一格式化 AI 对话时间，缺失时返回稳定兜底文案。
 */
function formatConversationTime(value: string | null | undefined): string {
  return value ? formatDateTime(value) : "未记录时间";
}

/**
 * 归一化统计导出里附带的多轮对话消息，避免把空消息一并渲染到导出结果中。
 */
function normalizeConversationMessages(
  messages: AIChatMessage[] | undefined,
): NormalizedConversationMessage[] {
  return (messages ?? [])
    .map((item) => ({
      role: item.role,
      content: item.content.trim(),
      createdAt: item.createdAt ?? null,
    }))
    .filter((item) => item.content.length > 0);
}

/**
 * 预先把对话消息整理成 SVG 里可直接摆放的消息块，并计算每块所需高度。
 */
function buildConversationSvgBlocks(
  messages: NormalizedConversationMessage[],
): ConversationSvgBlock[] {
  return messages.map((message) => {
    const roleLabel = message.role === "assistant" ? "AI 助理" : "你";
    const contentLines = wrapText(message.content, 42);
    const contentLineCount = Math.max(contentLines.length, 1);
    return {
      role: message.role,
      headerText: `${roleLabel} · ${formatConversationTime(message.createdAt)}`,
      contentLines,
      height: 54 + contentLineCount * 20,
    };
  });
}

/**
 * 计算“关键发现”面板的实际高度。
 * 这里按真实文本行数动态增高，避免长发现结论把底部面板内容裁掉。
 */
function resolveFindingsPanelHeight(findings: string[]): number {
  let contentHeight = 112;

  for (const finding of findings.slice(0, 5)) {
    const findingLines = wrapText(finding, 28);
    contentHeight += 24 + findingLines.length * 22 + 18;
  }

  return Math.max(MIN_FINDINGS_PANEL_HEIGHT, contentHeight + 24);
}

/**
 * 计算 AI 面板的实际高度。
 * 主分析正文和多轮追问都会计入总高度，导出图片不再依赖固定 500px 容器。
 */
function resolveAiPanelHeight(
  aiAnalysisLines: string[],
  conversationBlocks: ConversationSvgBlock[],
): number {
  let contentHeight = 138 + Math.max(aiAnalysisLines.length, 1) * 24 + 24;

  if (conversationBlocks.length > 0) {
    contentHeight += 54;
    for (const block of conversationBlocks) {
      contentHeight += block.height + 14;
    }
  }

  return Math.max(MIN_AI_PANEL_HEIGHT, contentHeight + 24);
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
      const rowY = index * 62;
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
 * 构造缺陷分布条形图。
 */
function buildDefectRows(payload: StatisticsReportPayload): string {
  const topItems = payload.overview.defectDistribution.slice(0, 6);
  const maxCount = Math.max(...topItems.map((item) => item.count), 1);

  return topItems
    .map((item, index) => {
      const rowY = index * 52;
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
 * 构造“关键发现”区域的 SVG 内容。
 */
function buildFindingsSvg(findings: string[]): string {
  let cursorY = 120;

  return findings
    .slice(0, 5)
    .map((finding, index) => {
      const lines = wrapText(finding, 28);
      const lineCount = Math.max(lines.length, 1);
      const itemY = cursorY;
      cursorY += 24 + lineCount * 22 + 18;
      return `
        <g transform="translate(28 ${itemY})">
          <circle cx="10" cy="-10" r="10" fill="#7fe4d0" />
          <text x="10" y="-6" fill="#082034" font-size="11" font-weight="700" text-anchor="middle">${index + 1}</text>
          <text x="32" y="0" fill="#dbe7f3" font-size="15">
            ${buildSvgTextBlock(lines, 32, 22)}
          </text>
        </g>
      `;
    })
    .join("");
}

/**
 * 构造 AI 面板里的多轮追问气泡内容。
 */
function buildConversationSvg(blocks: ConversationSvgBlock[]): string {
  let cursorY = 0;

  return blocks
    .map((block) => {
      const blockY = cursorY;
      cursorY += block.height + 14;
      const fill = block.role === "assistant" ? "rgba(255,255,255,0.03)" : "rgba(47,182,162,0.12)";
      const stroke = block.role === "assistant" ? "rgba(149,184,223,0.12)" : "rgba(47,182,162,0.28)";
      return `
        <g transform="translate(0 ${blockY})">
          <rect width="694" height="${block.height}" rx="18" fill="${fill}" stroke="${stroke}" />
          <text x="20" y="24" fill="#8ea4bd" font-size="12">${escapeMarkup(block.headerText)}</text>
          <text x="20" y="52" fill="#dbe7f3" font-size="14">
            ${buildSvgTextBlock(block.contentLines, 20, 20)}
          </text>
        </g>
      `;
    })
    .join("");
}

/**
 * 构造海报图顶部的摘要卡片。
 * 与长图不同，这里强调“适合汇报的一眼看懂”，因此统一使用更明亮的卡片样式。
 */
function buildPosterSummaryCards(payload: StatisticsReportPayload): string {
  const { summary } = payload.overview;
  const cardItems = [
    {
      title: "总检测量",
      value: `${summary.totalCount}`,
      hint: "当前窗口全部检测记录",
      accent: "#18b89a",
      x: 40,
    },
    {
      title: "当前良率",
      value: formatPercent(summary.passRate),
      hint: `良品 ${summary.goodCount} / 不良 ${summary.badCount}`,
      accent: "#3cc782",
      x: 425,
    },
    {
      title: "待确认",
      value: `${summary.uncertainCount}`,
      hint: "需要复核或补证据确认",
      accent: "#f3bf4d",
      x: 810,
    },
    {
      title: "待审核",
      value: `${summary.pendingReviewCount}`,
      hint: `已审核 ${summary.reviewedCount} 条`,
      accent: "#5b8ff9",
      x: 1195,
    },
  ];

  return cardItems
    .map((item) => `
      <g transform="translate(${item.x} 290)">
        <rect width="365" height="150" rx="26" fill="#ffffff" filter="url(#posterCardShadow)" />
        <rect x="22" y="20" width="52" height="6" rx="3" fill="${item.accent}" />
        <text x="22" y="54" fill="#67809a" font-size="16" font-weight="700">${escapeMarkup(item.title)}</text>
        <text x="22" y="104" fill="#11263d" font-size="44" font-weight="700">${escapeMarkup(item.value)}</text>
        <text x="22" y="132" fill="#8aa0b7" font-size="14">${escapeMarkup(item.hint)}</text>
      </g>
    `)
    .join("");
}

/**
 * 生成海报图中的缺陷分布条目。
 * 海报图只保留最关键的前三项，避免右上角再次变成拥挤的小报表。
 */
function buildPosterDefectRows(payload: StatisticsReportPayload): string {
  const topItems = payload.overview.defectDistribution.slice(0, 3);
  const maxCount = Math.max(...topItems.map((item) => item.count), 1);

  return topItems
    .map((item, index) => {
      const rowY = index * 42;
      const barWidth = (item.count / maxCount) * 170;
      return `
        <g transform="translate(0 ${rowY})">
          <text x="0" y="14" fill="#11263d" font-size="14" font-weight="700">${escapeMarkup(item.defectType)}</text>
          <text x="170" y="14" fill="#16a085" font-size="14" font-weight="700" text-anchor="end">${item.count}</text>
          <rect x="0" y="24" width="170" height="8" rx="4" fill="#e7eef5" />
          <rect x="0" y="24" width="${barWidth.toFixed(1)}" height="8" rx="4" fill="#18b89a" />
        </g>
      `;
    })
    .join("");
}

/**
 * 生成海报图中的结果结构条目。
 * 结果结构单独放在一个小卡片里，避免和缺陷 Top 列表互相抢空间。
 */
function buildPosterResultDistributionRows(payload: StatisticsReportPayload): string {
  const { overview } = payload;
  const maxCount = Math.max(...overview.resultDistribution.map((item) => item.count), 1);

  return overview.resultDistribution
    .map((item, index) => {
      const rowY = index * 40;
      const label = item.result === "good" ? "良品" : item.result === "bad" ? "不良" : "待确认";
      const color = item.result === "good" ? "#3cc782" : item.result === "bad" ? "#ff7a6d" : "#f3bf4d";
      const barWidth = (item.count / maxCount) * 178;
      return `
        <g transform="translate(0 ${rowY})">
          <text x="0" y="14" fill="#425d77" font-size="13">${label}</text>
          <text x="178" y="14" fill="${color}" font-size="14" font-weight="700" text-anchor="end">${item.count}</text>
          <rect x="0" y="24" width="178" height="8" rx="4" fill="#e7eef5" />
          <rect x="0" y="24" width="${barWidth.toFixed(1)}" height="8" rx="4" fill="${color}" />
        </g>
      `;
    })
    .join("");
}

/**
 * 生成海报图中的审核状态卡片。
 * 审核状态改为卡片摘要，而不是继续塞一列很小的文字，保证海报图更像“总览海报”。
 */
function buildPosterReviewStatusCards(payload: StatisticsReportPayload): string {
  return payload.overview.reviewStatusDistribution
    .map((item, index) => {
      const label = item.reviewStatus === "reviewed"
        ? "已审核"
        : item.reviewStatus === "ai_reserved"
          ? "AI 预留"
          : "待审核";
      const color = item.reviewStatus === "reviewed"
        ? "#3cc782"
        : item.reviewStatus === "ai_reserved"
          ? "#5b8ff9"
          : "#f3bf4d";
      const x = index * 150;
      return `
        <g transform="translate(${x} 0)">
          <rect width="138" height="48" rx="16" fill="#ffffff" />
          <circle cx="16" cy="18" r="6" fill="${color}" />
          <text x="30" y="22" fill="#607b95" font-size="12">${label}</text>
          <text x="18" y="40" fill="#11263d" font-size="18" font-weight="700">${item.count}</text>
        </g>
      `;
    })
    .join("");
}

/**
 * 生成海报图中的排行行。
 * 这里故意只保留前四项，并使用更大的字号和更稀疏的间距，让分享图更好读。
 */
function buildPosterRankingRows<TItem extends PartQualityItem | DeviceQualityItem>(
  items: TItem[],
  options: {
    labelResolver: (item: TItem) => string;
  },
): string {
  const visibleItems = items.slice(0, 4);
  const maxRiskCount = Math.max(...visibleItems.map((item) => item.badCount + item.uncertainCount), 1);

  return visibleItems
    .map((item, index) => {
      const rowY = index * 76;
      const riskCount = item.badCount + item.uncertainCount;
      const barWidth = (riskCount / maxRiskCount) * 420;
      const labelLines = clampLines(wrapText(options.labelResolver(item), 26), 1);
      return `
        <g transform="translate(0 ${rowY})">
          <circle cx="14" cy="18" r="14" fill="#e9f6f2" />
          <text x="14" y="23" fill="#148a74" font-size="14" font-weight="700" text-anchor="middle">${index + 1}</text>
          <text x="40" y="18" fill="#11263d" font-size="16" font-weight="700">${escapeMarkup(labelLines[0] ?? "")}</text>
          <text x="40" y="42" fill="#7088a2" font-size="13">总量 ${item.totalCount} | 不良 ${item.badCount} | 待确认 ${item.uncertainCount} | 良率 ${formatPercent(item.passRate)}</text>
          <rect x="40" y="54" width="420" height="8" rx="4" fill="#e8eef5" />
          <rect x="40" y="54" width="${barWidth.toFixed(1)}" height="8" rx="4" fill="#ff7a6d" />
        </g>
      `;
    })
    .join("");
}

/**
 * 生成海报图里的关键发现列表。
 * 关键发现保持“少而准”，控制在四条以内，避免整张图变成说明书。
 */
function buildPosterFindingsList(findings: string[]): string {
  let cursorY = 0;

  return findings
    .slice(0, 4)
    .map((finding, index) => {
      const lines = clampLines(wrapText(finding, 28), 3);
      const itemHeight = 28 + Math.max(lines.length, 1) * 22 + 20;
      const itemY = cursorY;
      cursorY += itemHeight;
      return `
        <g transform="translate(0 ${itemY})">
          <circle cx="14" cy="12" r="14" fill="#e8f6f2" />
          <text x="14" y="17" fill="#148a74" font-size="14" font-weight="700" text-anchor="middle">${index + 1}</text>
          <text x="40" y="18" fill="#17314c" font-size="15">
            ${buildSvgTextBlock(lines, 40, 22)}
          </text>
        </g>
      `;
    })
    .join("");
}

/**
 * 生成海报图中的“最近追问摘要”。
 * 海报图不再完整堆叠整段对话，只保留最近两条消息的摘要，让图片更适合转发和汇报。
 */
function buildPosterConversationPreview(messages: NormalizedConversationMessage[]): string {
  const previewMessages = messages.slice(-2);

  if (previewMessages.length === 0) {
    return `
      <rect x="0" y="0" width="720" height="86" rx="20" fill="#f5f8fb" />
      <text x="22" y="34" fill="#69829c" font-size="14">当前没有追问记录。</text>
      <text x="22" y="58" fill="#8ca1b6" font-size="13">如需保留完整 AI 对话，请使用 PDF 导出。</text>
    `;
  }

  return previewMessages
    .map((message, index) => {
      const roleLabel = message.role === "assistant" ? "AI 助理" : "你";
      const contentLines = clampLines(wrapText(message.content, 34), 2);
      const boxY = index * 98;
      const fill = message.role === "assistant" ? "#f5f9ff" : "#eefaf6";
      const stroke = message.role === "assistant" ? "#dce7f2" : "#cdece1";
      return `
        <g transform="translate(0 ${boxY})">
          <rect width="720" height="86" rx="20" fill="${fill}" stroke="${stroke}" />
          <text x="20" y="26" fill="#6e86a0" font-size="12" font-weight="700">${escapeMarkup(roleLabel)} · ${escapeMarkup(formatConversationTime(message.createdAt))}</text>
          <text x="20" y="52" fill="#17314c" font-size="14">
            ${buildSvgTextBlock(contentLines, 20, 18)}
          </text>
        </g>
      `;
    })
    .join("");
}

/**
 * 构造适合分享和汇报的统计海报 SVG。
 * 这版图片不再追求“完整留档”，而是固定高度、强调重点信息，并把完整明细让给 PDF。
 */
function buildStatisticsPosterSvgDocument(payload: StatisticsReportPayload): StatisticsReportSvgDocument {
  const { overview, aiAnalysis } = payload;
  const trendRect = {
    x: 0,
    y: 0,
    width: 760,
    height: 220,
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
  const axisTicks = buildTrendAxisTicks(overview.dailyTrend);
  const findings = overview.keyFindings.length > 0
    ? overview.keyFindings
    : ["当前窗口暂无系统提炼的关键发现，建议先生成 AI 批次分析后再导出。"];
  const aiSummaryLines = clampLines(
    wrapText(
      aiAnalysis?.answer.trim()
        ? aiAnalysis.answer
        : "尚未生成 AI 批次分析。海报图会保留统计趋势与风险结构，完整 AI 全文建议通过 PDF 导出。",
      37,
    ),
    7,
  );
  const normalizedMessages = normalizeConversationMessages(payload.aiConversation);
  const partGroupLabel = overview.sampleGallery.totalPartCount > 0
    ? `${overview.sampleGallery.totalPartCount} 个零件分类`
    : "未生成分类图像摘要";
  const sampleImageLabel = overview.sampleGallery.totalImageCount > 0
    ? `${overview.sampleGallery.totalImageCount} 张样本图`
    : "暂无样本图";
  const latestUploadLabel = overview.sampleGallery.latestUploadedAt
    ? formatDateTime(overview.sampleGallery.latestUploadedAt)
    : "暂无上传时间";

  return {
    width: POSTER_WIDTH,
    height: POSTER_HEIGHT,
    svgText: `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${POSTER_WIDTH}" height="${POSTER_HEIGHT}" viewBox="0 0 ${POSTER_WIDTH} ${POSTER_HEIGHT}">
  <defs>
    <linearGradient id="posterBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#f4f7fb" />
      <stop offset="100%" stop-color="#eaf0f7" />
    </linearGradient>
    <linearGradient id="posterHeroBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10233a" />
      <stop offset="100%" stop-color="#164972" />
    </linearGradient>
    <linearGradient id="posterTrendArea" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#18b89a" stop-opacity="0.24" />
      <stop offset="100%" stop-color="#18b89a" stop-opacity="0.02" />
    </linearGradient>
    <filter id="posterCardShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="14" stdDeviation="20" flood-color="#123250" flood-opacity="0.10" />
    </filter>
  </defs>

  <rect width="${POSTER_WIDTH}" height="${POSTER_HEIGHT}" fill="url(#posterBg)" />
  <circle cx="1480" cy="120" r="220" fill="#d9eef1" />
  <circle cx="126" cy="1720" r="200" fill="#e1ecff" />

  <g transform="translate(40 40)">
    <rect width="1520" height="210" rx="34" fill="url(#posterHeroBg)" />
    <circle cx="1340" cy="38" r="124" fill="#24d0ba" opacity="0.10" />
    <circle cx="1450" cy="170" r="88" fill="#6aa7ff" opacity="0.16" />
    <text x="36" y="46" fill="#82e8d7" font-size="18" font-weight="700" letter-spacing="2">STATISTICS POSTER</text>
    <text x="36" y="102" fill="#ffffff" font-size="42" font-weight="700">产品批次统计海报</text>
    <text x="36" y="132" fill="#c8d7e8" font-size="16">${escapeMarkup(buildScopeSummary(payload))}</text>
    <text x="36" y="160" fill="#c8d7e8" font-size="14">生成时间：${escapeMarkup(formatDateTime(overview.generatedAt))}</text>

    <g transform="translate(36 176)">
      <rect width="250" height="42" rx="21" fill="rgba(255,255,255,0.10)" />
      <text x="18" y="27" fill="#eff8ff" font-size="14">分类覆盖：${escapeMarkup(partGroupLabel)}</text>
    </g>
    <g transform="translate(304 176)">
      <rect width="230" height="42" rx="21" fill="rgba(255,255,255,0.10)" />
      <text x="18" y="27" fill="#eff8ff" font-size="14">样本图片：${escapeMarkup(sampleImageLabel)}</text>
    </g>
    <g transform="translate(552 176)">
      <rect width="450" height="42" rx="21" fill="rgba(255,255,255,0.10)" />
      <text x="18" y="27" fill="#eff8ff" font-size="14">最近上传：${escapeMarkup(latestUploadLabel)}</text>
    </g>
  </g>

  ${buildPosterSummaryCards(payload)}

  <g transform="translate(40 470)">
    <rect width="970" height="420" rx="30" fill="#ffffff" filter="url(#posterCardShadow)" />
    <text x="28" y="42" fill="#11263d" font-size="26" font-weight="700">趋势曲线</text>
    <text x="28" y="68" fill="#7289a2" font-size="14">总量、不良、待确认在当前窗口内的变化</text>
    <g transform="translate(106 118)">
      <line x1="0" y1="220" x2="760" y2="220" stroke="#d8e3ef" />
      <line x1="0" y1="0" x2="0" y2="220" stroke="#d8e3ef" />
      ${valueTicks
        .map((item) => {
          const y = (220 - 220 * item.ratio).toFixed(1);
          return `
            <line x1="0" y1="${y}" x2="760" y2="${y}" stroke="#ecf1f6" stroke-dasharray="8 8" />
            <text x="-14" y="${Number(y) + 4}" fill="#7f96ae" font-size="11" text-anchor="end">${escapeMarkup(item.label)}</text>
          `;
        })
        .join("")}
      <path fill="url(#posterTrendArea)" stroke="none" d="${buildTrendAreaPath(totalSeries, 220)}" />
      <path fill="none" stroke="#18b89a" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="${buildTrendSmoothPath(totalSeries)}" />
      <path fill="none" stroke="#ff7a6d" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="${buildTrendSmoothPath(badSeries)}" />
      <path fill="none" stroke="#f3bf4d" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="${buildTrendSmoothPath(uncertainSeries)}" />
      ${[totalSeries, badSeries, uncertainSeries]
        .map((seriesPoints, seriesIndex) => {
          const color = seriesIndex === 0 ? "#18b89a" : seriesIndex === 1 ? "#ff7a6d" : "#f3bf4d";
          return seriesPoints
            .map(
              (point) => `<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3.8" fill="${color}" stroke="#ffffff" stroke-width="1.4" />`,
            )
            .join("");
        })
        .join("")}
      ${axisTicks
        .map((item) => {
          const point = totalSeries[item.index] ?? totalSeries[0];
          return `<text x="${point.x.toFixed(1)}" y="248" fill="#7f96ae" font-size="11" text-anchor="middle">${escapeMarkup(item.label)}</text>`;
        })
        .join("")}
    </g>
    <g transform="translate(28 372)">
      <circle cx="12" cy="0" r="6" fill="#18b89a" />
      <text x="28" y="5" fill="#425d77" font-size="14">总量</text>
      <circle cx="104" cy="0" r="6" fill="#ff7a6d" />
      <text x="120" y="5" fill="#425d77" font-size="14">不良</text>
      <circle cx="196" cy="0" r="6" fill="#f3bf4d" />
      <text x="212" y="5" fill="#425d77" font-size="14">待确认</text>
    </g>
  </g>

  <g transform="translate(1030 470)">
    <rect width="530" height="420" rx="30" fill="#ffffff" filter="url(#posterCardShadow)" />
    <text x="28" y="42" fill="#11263d" font-size="26" font-weight="700">缺陷与结构</text>
    <text x="28" y="68" fill="#7289a2" font-size="14">把缺陷、结果结构和审核状态拆开后，一眼更容易看懂。</text>

    <g transform="translate(28 108)">
      <rect width="198" height="172" rx="22" fill="#f7fafc" />
      <text x="16" y="28" fill="#5f7892" font-size="13" font-weight="700">缺陷 Top3</text>
      <g transform="translate(16 56)">
        ${buildPosterDefectRows(payload)}
      </g>
    </g>

    <g transform="translate(246 108)">
      <rect width="256" height="172" rx="22" fill="#f7fafc" />
      <text x="16" y="28" fill="#5f7892" font-size="13" font-weight="700">结果结构</text>
      <g transform="translate(16 56)">
        ${buildPosterResultDistributionRows(payload)}
      </g>
    </g>

    <g transform="translate(28 300)">
      <rect width="474" height="92" rx="22" fill="#f7fafc" />
      <text x="16" y="26" fill="#5f7892" font-size="13" font-weight="700">审核状态</text>
      <g transform="translate(16 34)">
        ${buildPosterReviewStatusCards(payload)}
      </g>
    </g>
  </g>

  <g transform="translate(40 920)">
    <rect width="740" height="390" rx="30" fill="#ffffff" filter="url(#posterCardShadow)" />
    <text x="28" y="42" fill="#11263d" font-size="26" font-weight="700">零件风险排行</text>
    <text x="28" y="68" fill="#7289a2" font-size="14">优先定位质量压力更高的零件类别</text>
    <g transform="translate(28 118)">
      ${buildPosterRankingRows(overview.partQualityRanking, {
        labelResolver: (item) => `${item.partName} / ${item.partCode}`,
      })}
    </g>
  </g>

  <g transform="translate(820 920)">
    <rect width="740" height="390" rx="30" fill="#ffffff" filter="url(#posterCardShadow)" />
    <text x="28" y="42" fill="#11263d" font-size="26" font-weight="700">设备风险排行</text>
    <text x="28" y="68" fill="#7289a2" font-size="14">帮助判断问题偏向设备链路还是产品侧</text>
    <g transform="translate(28 118)">
      ${buildPosterRankingRows(overview.deviceQualityRanking, {
        labelResolver: (item) => `${item.deviceName} / ${item.deviceCode}`,
      })}
    </g>
  </g>

  <g transform="translate(40 1340)">
    <rect width="700" height="470" rx="30" fill="#ffffff" filter="url(#posterCardShadow)" />
    <text x="28" y="42" fill="#11263d" font-size="26" font-weight="700">关键发现</text>
    <text x="28" y="68" fill="#7289a2" font-size="14">系统基于当前统计窗口提炼的重点观察</text>
    <g transform="translate(28 116)">
      ${buildPosterFindingsList(findings)}
    </g>
  </g>

  <g transform="translate(760 1340)">
    <rect width="800" height="470" rx="30" fill="#ffffff" filter="url(#posterCardShadow)" />
    <text x="28" y="42" fill="#11263d" font-size="26" font-weight="700">AI 批次摘要</text>
    <text x="28" y="68" fill="#7289a2" font-size="14">模型：${escapeMarkup(aiAnalysis?.providerHint ?? "未选择模型")} · 分析时间：${escapeMarkup(aiAnalysis ? formatDateTime(aiAnalysis.generatedAt) : "未生成")}</text>
    <text x="28" y="116" fill="#17314c" font-size="16">
      ${buildSvgTextBlock(aiSummaryLines, 28, 20)}
    </text>

    <text x="28" y="284" fill="#4e6983" font-size="15" font-weight="700">最近追问摘要</text>
    <g transform="translate(28 304)">
      ${buildPosterConversationPreview(normalizedMessages)}
    </g>

    <rect x="28" y="420" width="744" height="32" rx="16" fill="#eef3f8" />
    <text x="42" y="441" fill="#58718a" font-size="13">完整 AI 全文、追问记录与审计留档建议导出 PDF，不建议继续堆进图片。</text>
  </g>

  <g transform="translate(40 1842)">
    <text x="0" y="0" fill="#748ba4" font-size="13">图片导出方案：海报图用于汇报与分享，PDF 用于完整留档与全文阅读。</text>
    <text x="1520" y="0" fill="#748ba4" font-size="13" text-anchor="end">云端检测系统</text>
  </g>
</svg>`,
  };
}

/**
 * 生成适合分享的统计海报 SVG 文本。
 */
export function buildStatisticsPosterSvg(payload: StatisticsReportPayload): string {
  return buildStatisticsPosterSvgDocument(payload).svgText;
}

/**
 * 统一构造统计导出所需的 SVG 文档，并返回动态高度。
 */
function buildStatisticsReportSvgDocument(payload: StatisticsReportPayload): StatisticsReportSvgDocument {
  const { overview, aiAnalysis } = payload;
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
  const aiMainContent = aiAnalysis?.answer.trim()
    ? aiAnalysis.answer
    : "尚未生成 AI 批次分析，可先在统计页选择模型后发起分析。";
  const aiMainLines = wrapText(
    aiMainContent,
    34,
  );
  const conversationBlocks = buildConversationSvgBlocks(
    normalizeConversationMessages(payload.aiConversation),
  );
  const findingsPanelHeight = resolveFindingsPanelHeight(findings);
  const aiPanelHeight = resolveAiPanelHeight(aiMainLines, conversationBlocks);
  const bottomSectionHeight = Math.max(findingsPanelHeight, aiPanelHeight);
  const svgHeight = BASE_BOTTOM_SECTION_Y + bottomSectionHeight + SVG_BOTTOM_MARGIN;

  const aiMainTextHeight = Math.max(aiMainLines.length, 1) * 24;
  const aiConversationStartY = 138 + aiMainTextHeight + 36;
  const aiConversationGroupY = aiConversationStartY + 52;

  return {
    width: SVG_WIDTH,
    height: svgHeight,
    svgText: `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${SVG_WIDTH}" height="${svgHeight}" viewBox="0 0 ${SVG_WIDTH} ${svgHeight}">
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

  <rect width="${SVG_WIDTH}" height="${svgHeight}" fill="url(#reportBg)" />
  <circle cx="150" cy="120" r="180" fill="#1fae9b" opacity="0.12" />
  <circle cx="1240" cy="${Math.max(svgHeight - 160, 320)}" r="260" fill="#4f9fff" opacity="0.1" />

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

  <g transform="translate(60 ${BASE_BOTTOM_SECTION_Y})">
    <rect width="500" height="${findingsPanelHeight}" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">关键发现</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">系统根据统计结果自动提炼出的重点观察点</text>
    ${buildFindingsSvg(findings)}
  </g>

  <g transform="translate(590 ${BASE_BOTTOM_SECTION_Y})">
    <rect width="750" height="${aiPanelHeight}" rx="24" fill="#112740" stroke="url(#panelStroke)" />
    <text x="28" y="42" fill="#f8fbff" font-size="24" font-weight="700">AI 批次分析</text>
    <text x="28" y="68" fill="#8ea4bd" font-size="14">${escapeMarkup(aiAnalysis?.providerHint ?? "未选择模型")}</text>
    <text x="28" y="98" fill="#8ea4bd" font-size="13">分析时间：${escapeMarkup(aiAnalysis ? formatDateTime(aiAnalysis.generatedAt) : "未生成")}</text>
    <text x="28" y="138" fill="#dbe7f3" font-size="16">
      ${buildSvgTextBlock(aiMainLines, 28, 24)}
    </text>
    ${conversationBlocks.length > 0 ? `
      <text x="28" y="${aiConversationStartY}" fill="#f8fbff" font-size="20" font-weight="700">AI 追问记录</text>
      <text x="28" y="${aiConversationStartY + 24}" fill="#8ea4bd" font-size="13">导出时会一并保留统计页工作台中的后续追问与回答。</text>
      <g transform="translate(28 ${aiConversationGroupY})">
        ${buildConversationSvg(conversationBlocks)}
      </g>
    ` : ""}
  </g>
</svg>`,
  };
}

/**
 * 生成统计导出所需的 SVG 文本。
 */
export function buildStatisticsReportSvg(payload: StatisticsReportPayload): string {
  return buildStatisticsReportSvgDocument(payload).svgText;
}

/**
 * 统一下载 Blob，避免图片导出和其它下载流程重复写锚点逻辑。
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
 * 这里直接使用动态 SVG 高度创建画布，避免长 AI 文本在底部被裁切。
 */
export async function exportStatisticsReportPng(payload: StatisticsReportPayload): Promise<void> {
  /**
   * PNG 导出走固定高度的“汇报海报图”方案。
   * 完整 AI 正文和完整追问记录继续交给 PDF，避免图片导出变成超长证据卷轴。
   */
  const svgDocument = buildStatisticsPosterSvgDocument(payload);
  const svgBlob = new Blob([svgDocument.svgText], { type: "image/svg+xml;charset=utf-8" });
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
    canvas.width = svgDocument.width * scale;
    canvas.height = svgDocument.height * scale;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("浏览器当前无法创建图片导出画布");
    }

    context.scale(scale, scale);
    context.drawImage(image, 0, 0, svgDocument.width, svgDocument.height);

    const pngBlob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error("统计报告 PNG 导出失败"));
          return;
        }
        resolve(blob);
      }, "image/png");
    });

    downloadBlob(pngBlob, `statistics-poster-${Date.now()}.png`);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}

/**
 * 生成打印用 HTML，让浏览器直接走“另存为 PDF”流程。
 * 该版本也会把统计页里的多轮追问记录完整补到正文区域里。
 */
function buildStatisticsReportHtml(payload: StatisticsReportPayload): string {
  const svgMarkup = buildStatisticsReportSvg(payload).replace(/^<\?xml[^>]*>\s*/, "");
  const aiAnswer = escapeMarkup(payload.aiAnalysis?.answer ?? "尚未生成 AI 批次分析。");
  const keyFindingItems = payload.overview.keyFindings
    .map((item) => `<li>${escapeMarkup(item)}</li>`)
    .join("");
  const conversationMessages = normalizeConversationMessages(payload.aiConversation);
  const conversationMarkup = conversationMessages.length > 0
    ? conversationMessages
      .map((item) => {
        const roleLabel = item.role === "assistant" ? "AI 助理" : "你";
        const timeText = formatConversationTime(item.createdAt);
        const modifierClass = item.role === "assistant"
          ? "conversation-item--assistant"
          : "conversation-item--user";
        return `
          <article class="conversation-item ${modifierClass}">
            <div class="conversation-item__meta">
              <strong>${escapeMarkup(roleLabel)}</strong>
              <span>${escapeMarkup(timeText)}</span>
            </div>
            <div class="conversation-item__content">${escapeMarkup(item.content)}</div>
          </article>
        `;
      })
      .join("")
    : "<p class='meta'>当前没有可导出的追问记录。</p>";

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
      .conversation-list {
        display: grid;
        gap: 14px;
      }
      .conversation-item {
        display: grid;
        gap: 10px;
        padding: 16px 18px;
        border-radius: 16px;
        border: 1px solid #d8e3ef;
      }
      .conversation-item--assistant {
        background: #f7fbff;
      }
      .conversation-item--user {
        background: #eefaf6;
        border-color: #cceee3;
      }
      .conversation-item__meta {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        color: #5a7089;
        font-size: 13px;
      }
      .conversation-item__content {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
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
      <section class="panel">
        <h2>AI 追问记录</h2>
        <div class="conversation-list">${conversationMarkup}</div>
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
   * 部分浏览器会在这种组合下直接保留一页空白 about:blank，
   * 导致用户看到白屏。改为先生成完整 HTML Blob，再通过 Blob URL 打开。
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
