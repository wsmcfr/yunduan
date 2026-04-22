"""轻量报表版 PDF 渲染器。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from math import ceil
from typing import Any

from src.core.errors import IntegrationError
from src.schemas.statistics import (
    StatisticsAIAnalysisResponse,
    StatisticsExportConversationMessage,
    StatisticsOverviewResponse,
)


@dataclass(slots=True)
class LightweightPdfTheme:
    """轻量 PDF 的配色和排版主题。

    这里把常用颜色集中起来，避免直接绘制版 PDF 到处散落十六进制色值。
    """

    navy: str = "#10233A"
    slate: str = "#5F7389"
    border: str = "#D8E3EF"
    mint: str = "#18A58D"
    green: str = "#33C07A"
    red: str = "#E76161"
    amber: str = "#F1B54B"
    blue: str = "#5D97F2"
    panel_bg: str = "#F8FBFF"
    page_bg: str = "#FFFFFF"


class StatisticsLightweightPdfRenderer:
    """负责直接绘制轻量报表版 PDF。

    这版 PDF 不再依赖 HTML/CSS 渲染，而是直接用矢量指令绘制：
    - 速度更稳定
    - 版式更像正式工业报告
    - 在保持性能可控的前提下，仍可附带少量代表样本图，保证信息完整性
    """

    def __init__(self) -> None:
        """初始化轻量 PDF 渲染器。"""

        self.theme = LightweightPdfTheme()

    def _load_reportlab(self) -> dict[str, Any]:
        """懒加载 reportlab 依赖。

        本地开发环境不一定预装 `reportlab`，因此不能在模块导入阶段就强依赖。
        真正执行轻量 PDF 导出时再检查依赖，可以让项目在未安装该库时仍能正常运行其它功能。
        """

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise IntegrationError(
                code="lightweight_pdf_renderer_unavailable",
                message="当前服务端尚未安装 reportlab，暂时无法生成轻量报表版 PDF。",
                details={
                    "hint": "请在后端虚拟环境安装 reportlab 后重试。",
                },
            ) from exc

        return {
            "colors": colors,
            "A4": A4,
            "mm": mm,
            "ImageReader": ImageReader,
            "pdfmetrics": pdfmetrics,
            "UnicodeCIDFont": UnicodeCIDFont,
            "canvas": canvas,
        }

    def _ensure_font_registered(self, *, pdfmetrics: Any, unicode_cid_font: Any) -> str:
        """注册轻量 PDF 使用的中文字体。

        直接绘制 PDF 时如果继续用 Helvetica，中文会变成空框。
        `STSong-Light` 是 reportlab 自带的 CJK 字体方案，不依赖额外字体文件，适合服务器环境。
        """

        font_name = "STSong-Light"
        # `getRegisteredFontNames()` 返回的是字体名字字符串列表，不是字体对象。
        # 这里如果继续按 `font.fontName` 访问，运行时就会直接抛 AttributeError，
        # 导致轻量 PDF 在真正导出时返回 500。
        registered_fonts = set(pdfmetrics.getRegisteredFontNames())
        if font_name not in registered_fonts:
            pdfmetrics.registerFont(unicode_cid_font(font_name))
        return font_name

    def _format_datetime(self, value: datetime | None) -> str:
        """把时间格式化成报表里可直接阅读的文本。"""

        if value is None:
            return "未记录"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _format_date_range(self, *, overview: StatisticsOverviewResponse) -> str:
        """拼装当前统计窗口的范围说明。"""

        scope_parts = [
            f"时间范围：{overview.filters.start_date or '未限定'} 至 {overview.filters.end_date or '未限定'}",
            f"窗口：{overview.filters.days} 天",
        ]
        if overview.filters.part_id is not None:
            scope_parts.append(f"零件 ID：{overview.filters.part_id}")
        if overview.filters.device_id is not None:
            scope_parts.append(f"设备 ID：{overview.filters.device_id}")
        return " | ".join(scope_parts)

    def _format_percent(self, value: float) -> str:
        """把比例统一格式化成百分比字符串。"""

        return f"{round(value * 100, 1)}%"

    def _wrap_text(
        self,
        *,
        pdfmetrics: Any,
        text: str,
        font_name: str,
        font_size: int,
        max_width: float,
    ) -> list[str]:
        """按给定宽度手工换行。

        直接绘制版 PDF 没有浏览器排版引擎，所以长文本必须自己算宽度后切行。
        """

        normalized_text = (text or "").replace("\r", "").strip()
        if not normalized_text:
            return []

        wrapped_lines: list[str] = []
        for paragraph in normalized_text.split("\n"):
            current_line = ""
            for char in paragraph:
                candidate_line = f"{current_line}{char}"
                if pdfmetrics.stringWidth(candidate_line, font_name, font_size) <= max_width:
                    current_line = candidate_line
                    continue

                if current_line:
                    wrapped_lines.append(current_line)
                current_line = char

            if current_line:
                wrapped_lines.append(current_line)
            if paragraph == "":
                wrapped_lines.append("")

        return wrapped_lines

    def _draw_page_background(
        self,
        *,
        canvas_obj: Any,
        page_width: float,
        page_height: float,
    ) -> None:
        """绘制每一页统一的纯色底板。"""

        canvas_obj.setFillColor(self.theme.page_bg)
        canvas_obj.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    def _draw_footer(
        self,
        *,
        canvas_obj: Any,
        page_width: float,
        font_name: str,
        page_number: int,
    ) -> None:
        """绘制轻量 PDF 的统一页脚。"""

        canvas_obj.setStrokeColor(self.theme.border)
        canvas_obj.line(20, 28, page_width - 20, 28)

        canvas_obj.setFillColor(self.theme.slate)
        canvas_obj.setFont(font_name, 8)
        canvas_obj.drawString(20, 15, "云端检测系统 · 轻量统计报告")
        canvas_obj.drawRightString(page_width - 20, 15, f"第 {page_number} 页")

    def _draw_page_title_block(
        self,
        *,
        canvas_obj: Any,
        font_name: str,
        title: str,
        description: str,
        page_width: float,
        page_height: float,
    ) -> float:
        """绘制二级页面的页头标题，并返回后续内容起点。"""

        canvas_obj.setFillColor(self.theme.navy)
        canvas_obj.setFont(font_name, 18)
        canvas_obj.drawString(28, page_height - 42, title)

        canvas_obj.setFillColor(self.theme.slate)
        canvas_obj.setFont(font_name, 9)
        canvas_obj.drawString(28, page_height - 60, description)
        canvas_obj.drawRightString(page_width - 28, page_height - 60, "轻量报表版")
        return page_height - 82

    def _draw_header(
        self,
        *,
        canvas_obj: Any,
        page_width: float,
        page_height: float,
        font_name: str,
        overview: StatisticsOverviewResponse,
    ) -> float:
        """绘制首页头部信息并返回下一个可用的纵向坐标。"""

        canvas_obj.setFillColor(self.theme.navy)
        canvas_obj.roundRect(20, page_height - 120, page_width - 40, 92, 18, fill=1, stroke=0)

        canvas_obj.setFillColor(self.theme.mint)
        canvas_obj.setFont(font_name, 10)
        canvas_obj.drawString(36, page_height - 50, "LIGHTWEIGHT STATISTICS REPORT")

        canvas_obj.setFillColor("#FFFFFF")
        canvas_obj.setFont(font_name, 21)
        canvas_obj.drawString(36, page_height - 74, "产品批次统计分析报告（轻量报表版）")

        canvas_obj.setFillColor("#D8E6F2")
        canvas_obj.setFont(font_name, 10)
        canvas_obj.drawString(36, page_height - 96, self._format_date_range(overview=overview))
        canvas_obj.drawRightString(
            page_width - 36,
            page_height - 96,
            f"生成时间：{self._format_datetime(overview.generated_at)}",
        )
        return page_height - 144

    def _draw_summary_cards(
        self,
        *,
        canvas_obj: Any,
        font_name: str,
        page_width: float,
        top_y: float,
        overview: StatisticsOverviewResponse,
    ) -> float:
        """绘制摘要卡片区。"""

        card_gap = 12
        card_width = (page_width - 40 - card_gap * 3) / 4
        card_height = 80
        start_x = 20
        summary_items = [
            ("总检测量", str(overview.summary.total_count), "当前窗口记录总数", self.theme.mint),
            ("当前良率", self._format_percent(overview.summary.pass_rate), "最终生效结果中的良品占比", self.theme.green),
            ("待确认", str(overview.summary.uncertain_count), "需要结合复核继续判断", self.theme.amber),
            ("待审核", str(overview.summary.pending_review_count), "仍待人工审核的记录", self.theme.blue),
        ]

        for index, (title, value, hint, accent_color) in enumerate(summary_items):
            card_x = start_x + index * (card_width + card_gap)
            canvas_obj.setFillColor(self.theme.panel_bg)
            canvas_obj.setStrokeColor(self.theme.border)
            canvas_obj.roundRect(card_x, top_y - card_height, card_width, card_height, 12, fill=1, stroke=1)

            canvas_obj.setFillColor(accent_color)
            canvas_obj.roundRect(card_x, top_y - 6, card_width, 6, 6, fill=1, stroke=0)

            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 10)
            canvas_obj.drawString(card_x + 12, top_y - 22, title)

            canvas_obj.setFillColor(self.theme.navy)
            canvas_obj.setFont(font_name, 18)
            canvas_obj.drawString(card_x + 12, top_y - 44, value)

            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 8)
            canvas_obj.drawString(card_x + 12, top_y - 61, hint)

        return top_y - card_height - 18

    def _draw_section_title(
        self,
        *,
        canvas_obj: Any,
        font_name: str,
        title: str,
        description: str,
        x: float,
        y: float,
    ) -> None:
        """绘制通用分节标题。"""

        canvas_obj.setFillColor(self.theme.navy)
        canvas_obj.setFont(font_name, 13)
        canvas_obj.drawString(x, y, title)

        canvas_obj.setFillColor(self.theme.slate)
        canvas_obj.setFont(font_name, 9)
        canvas_obj.drawString(x, y - 14, description)

    def _draw_trend_chart(
        self,
        *,
        canvas_obj: Any,
        colors: Any,
        font_name: str,
        overview: StatisticsOverviewResponse,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """直接绘制轻量版趋势图。"""

        canvas_obj.setFillColor(self.theme.panel_bg)
        canvas_obj.setStrokeColor(self.theme.border)
        canvas_obj.roundRect(x, y - height, width, height, 14, fill=1, stroke=1)
        self._draw_section_title(
            canvas_obj=canvas_obj,
            font_name=font_name,
            title="趋势曲线",
            description="直接绘制矢量折线，聚焦总量、不良与待确认的变化。",
            x=x + 16,
            y=y - 18,
        )

        items = overview.daily_trend
        chart_left = x + 44
        chart_bottom = y - height + 32
        chart_width = width - 64
        chart_height = height - 76
        if not items:
            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 10)
            canvas_obj.drawString(x + 16, y - 70, "当前窗口没有趋势数据。")
            return

        max_value = max(
            max(item.total_count, item.bad_count, item.uncertain_count)
            for item in items
        ) or 1
        axis_max = ceil(max_value / 5) * 5 if max_value > 5 else max_value
        axis_max = max(axis_max, 1)

        canvas_obj.setStrokeColor(colors.HexColor(self.theme.border))
        canvas_obj.line(chart_left, chart_bottom, chart_left + chart_width, chart_bottom)
        canvas_obj.line(chart_left, chart_bottom, chart_left, chart_bottom + chart_height)

        for tick_index in range(4):
            ratio = tick_index / 3
            tick_value = axis_max * ratio
            tick_y = chart_bottom + chart_height * ratio
            canvas_obj.setStrokeColor(colors.HexColor("#EAF1F7"))
            canvas_obj.setDash(2, 3)
            canvas_obj.line(chart_left, tick_y, chart_left + chart_width, tick_y)
            canvas_obj.setDash()
            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 8)
            canvas_obj.drawRightString(chart_left - 6, tick_y - 2, str(int(round(tick_value))))

        series_definitions = [
            ("总量", self.theme.mint, [item.total_count for item in items]),
            ("不良", self.theme.red, [item.bad_count for item in items]),
            ("待确认", self.theme.amber, [item.uncertain_count for item in items]),
        ]

        for _, color_hex, values in series_definitions:
            canvas_obj.setStrokeColor(colors.HexColor(color_hex))
            canvas_obj.setLineWidth(2)
            points: list[tuple[float, float]] = []
            for index, value in enumerate(values):
                point_x = (
                    chart_left + chart_width * (0.5 if len(values) == 1 else index / (len(values) - 1))
                )
                point_y = chart_bottom + chart_height * (value / axis_max)
                points.append((point_x, point_y))

            for point_index in range(len(points) - 1):
                current_point = points[point_index]
                next_point = points[point_index + 1]
                canvas_obj.line(current_point[0], current_point[1], next_point[0], next_point[1])

            for point_x, point_y in points:
                canvas_obj.setFillColor(colors.HexColor(color_hex))
                canvas_obj.circle(point_x, point_y, 2.4, fill=1, stroke=0)

        canvas_obj.setFillColor(self.theme.slate)
        canvas_obj.setFont(font_name, 8)
        for index, item in enumerate(items):
            label_x = chart_left + chart_width * (0.5 if len(items) == 1 else index / (len(items) - 1))
            canvas_obj.drawCentredString(label_x, chart_bottom - 14, item.date.strftime("%m-%d"))

        legend_x = x + 18
        legend_y = y - height + 14
        for index, (label, color_hex, _) in enumerate(series_definitions):
            item_x = legend_x + index * 88
            canvas_obj.setFillColor(colors.HexColor(color_hex))
            canvas_obj.circle(item_x, legend_y, 3.2, fill=1, stroke=0)
            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 8)
            canvas_obj.drawString(item_x + 8, legend_y - 3, label)

    def _draw_defect_distribution(
        self,
        *,
        canvas_obj: Any,
        colors: Any,
        font_name: str,
        overview: StatisticsOverviewResponse,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """绘制缺陷分布条形图。"""

        canvas_obj.setFillColor(self.theme.panel_bg)
        canvas_obj.setStrokeColor(self.theme.border)
        canvas_obj.roundRect(x, y - height, width, height, 14, fill=1, stroke=1)
        self._draw_section_title(
            canvas_obj=canvas_obj,
            font_name=font_name,
            title="缺陷分布",
            description="保留当前窗口下最集中的缺陷类型。",
            x=x + 16,
            y=y - 18,
        )

        top_items = overview.defect_distribution[:5]
        if not top_items:
            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 10)
            canvas_obj.drawString(x + 16, y - 70, "当前窗口没有缺陷分布数据。")
            return

        max_count = max(item.count for item in top_items) or 1
        for index, item in enumerate(top_items):
            row_y = y - 54 - index * 28
            bar_width = (width - 120) * (item.count / max_count)
            canvas_obj.setFillColor(self.theme.navy)
            canvas_obj.setFont(font_name, 9)
            canvas_obj.drawString(x + 16, row_y, item.defect_type)

            canvas_obj.setFillColor(colors.HexColor("#EEF3F8"))
            canvas_obj.roundRect(x + 16, row_y - 12, width - 120, 8, 4, fill=1, stroke=0)
            canvas_obj.setFillColor(colors.HexColor(self.theme.mint))
            canvas_obj.roundRect(x + 16, row_y - 12, bar_width, 8, 4, fill=1, stroke=0)

            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.drawRightString(x + width - 16, row_y, str(item.count))

    def _draw_ranking_rows(
        self,
        *,
        canvas_obj: Any,
        colors: Any,
        font_name: str,
        title: str,
        description: str,
        rows: list[tuple[str, str, int, int, int, float]],
        x: float,
        y: float,
        width: float,
        height: float,
        accent_color: str,
    ) -> None:
        """绘制排行区块。"""

        canvas_obj.setFillColor(self.theme.panel_bg)
        canvas_obj.setStrokeColor(self.theme.border)
        canvas_obj.roundRect(x, y - height, width, height, 14, fill=1, stroke=1)
        self._draw_section_title(
            canvas_obj=canvas_obj,
            font_name=font_name,
            title=title,
            description=description,
            x=x + 16,
            y=y - 18,
        )

        if not rows:
            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 10)
            canvas_obj.drawString(x + 16, y - 70, "当前窗口没有排行数据。")
            return

        max_risk_count = max(bad_count + uncertain_count for _, _, _, bad_count, uncertain_count, _ in rows) or 1
        for index, row in enumerate(rows[:5]):
            label, code, total_count, bad_count, uncertain_count, pass_rate = row
            row_y = y - 54 - index * 42
            risk_count = bad_count + uncertain_count
            fill_width = (width - 120) * (risk_count / max_risk_count)

            canvas_obj.setFillColor(self.theme.navy)
            canvas_obj.setFont(font_name, 10)
            canvas_obj.drawString(x + 16, row_y, f"{label} / {code}")

            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 8)
            canvas_obj.drawString(
                x + 16,
                row_y - 12,
                f"总量 {total_count} | 不良 {bad_count} | 待确认 {uncertain_count} | 良率 {self._format_percent(pass_rate)}",
            )

            canvas_obj.setFillColor(colors.HexColor("#EEF3F8"))
            canvas_obj.roundRect(x + 16, row_y - 24, width - 120, 7, 3.5, fill=1, stroke=0)
            canvas_obj.setFillColor(colors.HexColor(accent_color))
            canvas_obj.roundRect(x + 16, row_y - 24, fill_width, 7, 3.5, fill=1, stroke=0)

    def _draw_bullet_list(
        self,
        *,
        canvas_obj: Any,
        pdfmetrics: Any,
        font_name: str,
        title: str,
        description: str,
        items: list[str],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """绘制关键发现或样本摘要这样的列表区块。"""

        canvas_obj.setFillColor(self.theme.panel_bg)
        canvas_obj.setStrokeColor(self.theme.border)
        canvas_obj.roundRect(x, y - height, width, height, 14, fill=1, stroke=1)
        self._draw_section_title(
            canvas_obj=canvas_obj,
            font_name=font_name,
            title=title,
            description=description,
            x=x + 16,
            y=y - 18,
        )

        current_y = y - 54
        panel_bottom = y - height + 18
        for item in items[:5]:
            wrapped_lines = self._wrap_text(
                pdfmetrics=pdfmetrics,
                text=item,
                font_name=font_name,
                font_size=9,
                max_width=width - 48,
            )[:3]
            if current_y <= panel_bottom:
                break
            canvas_obj.setFillColor(self.theme.mint)
            canvas_obj.circle(x + 20, current_y - 2, 2.8, fill=1, stroke=0)
            canvas_obj.setFillColor(self.theme.navy)
            canvas_obj.setFont(font_name, 9)
            for line in wrapped_lines:
                if current_y <= panel_bottom:
                    break
                canvas_obj.drawString(x + 30, current_y, line)
                current_y -= 12
            current_y -= 10

    def _build_sample_gallery_summary_items(
        self,
        *,
        overview: StatisticsOverviewResponse,
    ) -> list[str]:
        """把图库分组信息整理成适合轻量报表阅读的摘要条目。"""

        if overview.sample_gallery.groups:
            return [
                (
                    f"{group.part_name}（{group.part_code}）"
                    f"：记录 {group.record_count} 条，图片 {group.image_count} 张，"
                    f"最近上传 {self._format_datetime(group.latest_uploaded_at)}"
                )
                for group in overview.sample_gallery.groups[:5]
            ]

        return [
            (
                f"当前窗口共有 {overview.sample_gallery.total_record_count} 条记录，"
                f"{overview.sample_gallery.total_image_count} 张图片，暂无可展示的分类摘要。"
            )
        ]

    def _create_embedded_image_reader(
        self,
        *,
        image_reader_cls: Any,
        image_src: str,
    ) -> Any | None:
        """把 data URI 图片转换成 reportlab 可消费的图片对象。

        轻量版 PDF 从导出服务拿到的是内嵌的 data URI。
        这里单独做一次解析，避免在绘制代码里重复处理 base64 和异常分支。
        """

        normalized_image_src = image_src.strip()
        if not normalized_image_src or ";base64," not in normalized_image_src:
            return None

        try:
            _, encoded_payload = normalized_image_src.split(";base64,", 1)
            image_bytes = base64.b64decode(encoded_payload)
            return image_reader_cls(BytesIO(image_bytes))
        except Exception:
            return None

    def _draw_sample_image_card(
        self,
        *,
        canvas_obj: Any,
        colors: Any,
        image_reader_cls: Any,
        font_name: str,
        sample_image: dict[str, str],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """绘制单张代表样本图卡片。

        卡片同时保留：
        - 记录编号与最终结果；
        - 零件/设备摘要；
        - 缺陷说明与采集时间；
        - 图片本体或失败占位说明。
        """

        canvas_obj.setFillColor(self.theme.panel_bg)
        canvas_obj.setStrokeColor(self.theme.border)
        canvas_obj.roundRect(x, y - height, width, height, 14, fill=1, stroke=1)

        result_color = sample_image.get("result_color") or self.theme.blue
        canvas_obj.setFillColor(colors.HexColor(result_color))
        canvas_obj.roundRect(x, y - 6, width, 6, 6, fill=1, stroke=0)

        canvas_obj.setFillColor(self.theme.navy)
        canvas_obj.setFont(font_name, 11)
        canvas_obj.drawString(x + 14, y - 22, sample_image.get("record_no", "未命名记录"))

        canvas_obj.setFillColor(colors.HexColor(result_color))
        canvas_obj.setFont(font_name, 10)
        canvas_obj.drawRightString(
            x + width - 14,
            y - 22,
            sample_image.get("result_label", "未记录"),
        )

        meta_lines = [
            sample_image.get("title", "未记录零件与设备信息"),
            f"缺陷信息：{sample_image.get('defect_text', '未记录')}",
            f"采集时间：{sample_image.get('captured_at', '未记录')}",
        ]
        canvas_obj.setFillColor(self.theme.slate)
        canvas_obj.setFont(font_name, 8)
        current_meta_y = y - 38
        for meta_line in meta_lines:
            canvas_obj.drawString(x + 14, current_meta_y, meta_line)
            current_meta_y -= 12

        image_area_x = x + 14
        image_area_y = y - height + 18
        image_area_width = width - 28
        image_area_height = height - 94
        canvas_obj.setFillColor(colors.HexColor("#FDFEFF"))
        canvas_obj.setStrokeColor(colors.HexColor(self.theme.border))
        canvas_obj.roundRect(
            image_area_x,
            image_area_y,
            image_area_width,
            image_area_height,
            10,
            fill=1,
            stroke=1,
        )

        image_reader = self._create_embedded_image_reader(
            image_reader_cls=image_reader_cls,
            image_src=sample_image.get("image_src", ""),
        )
        if image_reader is not None:
            try:
                canvas_obj.drawImage(
                    image_reader,
                    image_area_x + 10,
                    image_area_y + 10,
                    image_area_width - 20,
                    image_area_height - 20,
                    preserveAspectRatio=True,
                    anchor="c",
                )
                return
            except Exception:
                image_reader = None

        canvas_obj.setFillColor(self.theme.slate)
        canvas_obj.setFont(font_name, 9)
        canvas_obj.drawCentredString(
            x + width / 2,
            image_area_y + image_area_height / 2,
            sample_image.get("image_message", "当前样本图片暂时无法嵌入轻量版 PDF。"),
        )

    def _draw_sample_image_pages(
        self,
        *,
        canvas_obj: Any,
        colors: Any,
        image_reader_cls: Any,
        font_name: str,
        page_width: float,
        page_height: float,
        sample_images: list[dict[str, str]],
        start_page_number: int,
    ) -> int:
        """在后续页面绘制代表样本图片。

        轻量版不再追求把整页图库完全重建，而是保留少量代表样本：
        - 满足“导出后仍能看到实际零件图片”的要求；
        - 通过固定每页两张卡片来保证版面稳定；
        - 图片过多时自动续页，不截断。
        """

        if not sample_images:
            return start_page_number

        current_page_number = start_page_number
        cards_per_page = 2
        card_width = page_width - 48
        card_height = 308
        card_gap = 16
        page_top = page_height - 94

        for page_index in range(ceil(len(sample_images) / cards_per_page)):
            canvas_obj.showPage()
            self._draw_page_background(
                canvas_obj=canvas_obj,
                page_width=page_width,
                page_height=page_height,
            )
            self._draw_page_title_block(
                canvas_obj=canvas_obj,
                font_name=font_name,
                title="代表样本图片",
                description="轻量版同样保留少量代表图片，便于结合真实零件图继续阅读统计结论。",
                page_width=page_width,
                page_height=page_height,
            )

            page_items = sample_images[
                page_index * cards_per_page:(page_index + 1) * cards_per_page
            ]
            for card_index, sample_image in enumerate(page_items):
                card_top_y = page_top - card_index * (card_height + card_gap)
                self._draw_sample_image_card(
                    canvas_obj=canvas_obj,
                    colors=colors,
                    image_reader_cls=image_reader_cls,
                    font_name=font_name,
                    sample_image=sample_image,
                    x=24,
                    y=card_top_y,
                    width=card_width,
                    height=card_height,
                )

            self._draw_footer(
                canvas_obj=canvas_obj,
                page_width=page_width,
                font_name=font_name,
                page_number=current_page_number,
            )
            current_page_number += 1

        return current_page_number

    def _draw_supporting_summary_page(
        self,
        *,
        canvas_obj: Any,
        pdfmetrics: Any,
        font_name: str,
        page_width: float,
        page_height: float,
        overview: StatisticsOverviewResponse,
    ) -> None:
        """绘制第二页的关键发现和图库摘要。"""

        supporting_top = self._draw_page_title_block(
            canvas_obj=canvas_obj,
            font_name=font_name,
            title="关键发现与样本摘要",
            description="轻量版把发现结论和图库摘要拆到单独页面，避免首页信息拥挤与跨页裁切。",
            page_width=page_width,
            page_height=page_height,
        )

        self._draw_bullet_list(
            canvas_obj=canvas_obj,
            pdfmetrics=pdfmetrics,
            font_name=font_name,
            title="关键发现",
            description="系统自动提炼出的重点观察点。",
            items=overview.key_findings or ["当前窗口暂无关键发现。"],
            x=20,
            y=supporting_top,
            width=page_width - 40,
            height=190,
        )
        self._draw_bullet_list(
            canvas_obj=canvas_obj,
            pdfmetrics=pdfmetrics,
            font_name=font_name,
            title="样本图库摘要",
            description="本页先看图库摘要，后续页面仍会补充少量代表图片，兼顾速度和信息完整性。",
            items=self._build_sample_gallery_summary_items(overview=overview),
            x=20,
            y=supporting_top - 208,
            width=page_width - 40,
            height=240,
        )

    def _draw_ai_analysis_pages(
        self,
        *,
        canvas_obj: Any,
        pdfmetrics: Any,
        font_name: str,
        page_width: float,
        page_height: float,
        ai_analysis: StatisticsAIAnalysisResponse | None,
        start_page_number: int,
    ) -> int:
        """在后续页面绘制 AI 批次分析全文。"""

        if ai_analysis is None:
            return start_page_number

        analysis_text = (
            ai_analysis.answer.strip()
            if ai_analysis.answer.strip()
            else "本次导出未附带 AI 批次分析内容。"
        )
        wrapped_lines = self._wrap_text(
            pdfmetrics=pdfmetrics,
            text=analysis_text,
            font_name=font_name,
            font_size=10,
            max_width=page_width - 72,
        )

        lines_per_page = 44
        current_page_number = start_page_number
        for page_index in range(max(1, ceil(len(wrapped_lines) / lines_per_page))):
            canvas_obj.showPage()
            self._draw_page_background(
                canvas_obj=canvas_obj,
                page_width=page_width,
                page_height=page_height,
            )

            canvas_obj.setFillColor(self.theme.navy)
            canvas_obj.setFont(font_name, 18)
            canvas_obj.drawString(28, page_height - 40, "AI 批次分析全文")

            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 9)
            provider_hint = ai_analysis.provider_hint or "未生成"
            generated_at = self._format_datetime(ai_analysis.generated_at)
            canvas_obj.drawString(28, page_height - 58, f"模型：{provider_hint} | 时间：{generated_at}")

            text_object = canvas_obj.beginText(28, page_height - 86)
            text_object.setFont(font_name, 10)
            text_object.setLeading(15)
            text_object.setFillColor(self.theme.navy)
            for line in wrapped_lines[page_index * lines_per_page:(page_index + 1) * lines_per_page]:
                text_object.textLine(line)
            canvas_obj.drawText(text_object)
            self._draw_footer(
                canvas_obj=canvas_obj,
                page_width=page_width,
                font_name=font_name,
                page_number=current_page_number,
            )
            current_page_number += 1

        return current_page_number

    def _draw_ai_conversation_pages(
        self,
        *,
        canvas_obj: Any,
        colors: Any,
        pdfmetrics: Any,
        font_name: str,
        page_width: float,
        page_height: float,
        ai_conversation: list[StatisticsExportConversationMessage],
        start_page_number: int,
    ) -> int:
        """在后续页面绘制 AI 追问记录。

        轻量版不走 HTML 排版，因此这里直接按消息块手工分页。
        每条消息都会保留角色、时间和正文，避免导出后只剩主分析结论而丢失追问上下文。
        """

        normalized_messages = [
            item for item in ai_conversation if item.content.strip()
        ]
        if not normalized_messages:
            return start_page_number

        current_page_number = start_page_number
        current_y = 0.0
        page_is_open = False
        panel_x = 24
        panel_width = page_width - 48
        panel_bottom_limit = 54
        meta_height = 44
        line_height = 15
        bottom_padding = 16
        block_gap = 14

        def open_page() -> None:
            """打开一页新的追问记录页，并在必要时为上一页补页脚。"""

            nonlocal current_page_number, current_y, page_is_open

            if page_is_open:
                self._draw_footer(
                    canvas_obj=canvas_obj,
                    page_width=page_width,
                    font_name=font_name,
                    page_number=current_page_number,
                )
                current_page_number += 1

            canvas_obj.showPage()
            self._draw_page_background(
                canvas_obj=canvas_obj,
                page_width=page_width,
                page_height=page_height,
            )
            current_y = self._draw_page_title_block(
                canvas_obj=canvas_obj,
                font_name=font_name,
                title="AI 追问记录",
                description="这里保留统计页工作台里的后续追问与回答，方便导出后继续回溯分析链路。",
                page_width=page_width,
                page_height=page_height,
            )
            page_is_open = True

        def resolve_chunk_line_capacity() -> int:
            """根据当前页剩余空间，计算这一页还能放下多少行消息正文。

            轻量 PDF 没有浏览器排版和自动分页能力，
            因此这里必须先把“消息头 + 正文 + 底部留白”的高度预算算出来，
            否则一条超长回复会整块画到页外，导致用户看到“导出没有上传完”。
            """

            available_height = current_y - panel_bottom_limit
            available_line_height = available_height - meta_height - bottom_padding
            if available_line_height <= 0:
                return 0
            return max(int(available_line_height // line_height), 1)

        def draw_message_chunk(
            *,
            role_label: str,
            created_at_label: str,
            lines: list[str],
            is_continued_chunk: bool,
            role: str,
        ) -> None:
            """绘制当前页中的一段消息内容。

            一条 AI 回复可能被拆成多个 chunk：
            - 首段保留原始角色信息
            - 后续段落追加“（续）”提示
            这样用户翻页时能明确知道这是同一轮回答的续页，而不是新的对话。
            """

            nonlocal current_y

            effective_lines = lines or [""]
            block_height = meta_height + len(effective_lines) * line_height + bottom_padding
            block_y = current_y - block_height
            fill_color = "#F7FBFF" if role == "assistant" else "#EEF9F4"
            stroke_color = "#D8E3EF" if role == "assistant" else "#CBEBDD"
            meta_label = (
                f"{role_label}（续） | {created_at_label}"
                if is_continued_chunk
                else f"{role_label} | {created_at_label}"
            )

            canvas_obj.setFillColor(colors.HexColor(fill_color))
            canvas_obj.setStrokeColor(colors.HexColor(stroke_color))
            canvas_obj.roundRect(
                panel_x,
                block_y,
                panel_width,
                block_height,
                12,
                fill=1,
                stroke=1,
            )

            canvas_obj.setFillColor(self.theme.slate)
            canvas_obj.setFont(font_name, 9)
            canvas_obj.drawString(
                panel_x + 14,
                current_y - 20,
                meta_label,
            )

            text_object = canvas_obj.beginText(panel_x + 14, current_y - 38)
            text_object.setFont(font_name, 10)
            text_object.setLeading(line_height)
            text_object.setFillColor(self.theme.navy)
            for line in effective_lines:
                text_object.textLine(line)
            canvas_obj.drawText(text_object)

            current_y = block_y - block_gap

        for item in normalized_messages:
            role_label = "AI 助理" if item.role == "assistant" else "你"
            wrapped_lines = self._wrap_text(
                pdfmetrics=pdfmetrics,
                text=item.content.strip(),
                font_name=font_name,
                font_size=10,
                max_width=panel_width - 28,
            )
            remaining_lines = wrapped_lines or [""]
            created_at_label = self._format_datetime(item.created_at)
            chunk_index = 0

            while remaining_lines:
                if (not page_is_open) or resolve_chunk_line_capacity() <= 0:
                    open_page()

                chunk_line_capacity = resolve_chunk_line_capacity()
                if chunk_line_capacity <= 0:
                    open_page()
                    chunk_line_capacity = max(resolve_chunk_line_capacity(), 1)

                chunk_lines = remaining_lines[:chunk_line_capacity]
                remaining_lines = remaining_lines[chunk_line_capacity:]
                draw_message_chunk(
                    role_label=role_label,
                    created_at_label=created_at_label,
                    lines=chunk_lines,
                    is_continued_chunk=chunk_index > 0,
                    role=item.role,
                )
                chunk_index += 1

        if page_is_open:
            self._draw_footer(
                canvas_obj=canvas_obj,
                page_width=page_width,
                font_name=font_name,
                page_number=current_page_number,
            )
            current_page_number += 1

        return current_page_number

    def build_pdf(
        self,
        *,
        overview: StatisticsOverviewResponse,
        ai_analysis: StatisticsAIAnalysisResponse | None,
        ai_conversation: list[StatisticsExportConversationMessage] | None = None,
        sample_images: list[dict[str, str]] | None = None,
    ) -> tuple[bytes, str]:
        """构建轻量报表版 PDF 字节流和文件名。"""

        reportlab_modules = self._load_reportlab()
        colors = reportlab_modules["colors"]
        page_width, page_height = reportlab_modules["A4"]
        font_name = self._ensure_font_registered(
            pdfmetrics=reportlab_modules["pdfmetrics"],
            unicode_cid_font=reportlab_modules["UnicodeCIDFont"],
        )

        buffer = BytesIO()
        canvas_obj = reportlab_modules["canvas"].Canvas(
            buffer,
            pagesize=reportlab_modules["A4"],
            pageCompression=1,
        )
        canvas_obj.setTitle("产品批次统计分析报告（轻量报表版）")
        canvas_obj.setAuthor("云端检测系统")

        self._draw_page_background(
            canvas_obj=canvas_obj,
            page_width=page_width,
            page_height=page_height,
        )
        current_top_y = self._draw_header(
            canvas_obj=canvas_obj,
            page_width=page_width,
            page_height=page_height,
            font_name=font_name,
            overview=overview,
        )
        current_top_y = self._draw_summary_cards(
            canvas_obj=canvas_obj,
            font_name=font_name,
            page_width=page_width,
            top_y=current_top_y,
            overview=overview,
        )

        self._draw_trend_chart(
            canvas_obj=canvas_obj,
            colors=colors,
            font_name=font_name,
            overview=overview,
            x=20,
            y=current_top_y,
            width=270,
            height=206,
        )
        self._draw_defect_distribution(
            canvas_obj=canvas_obj,
            colors=colors,
            font_name=font_name,
            overview=overview,
            x=305,
            y=current_top_y,
            width=270,
            height=206,
        )

        second_row_top = current_top_y - 224
        self._draw_ranking_rows(
            canvas_obj=canvas_obj,
            colors=colors,
            font_name=font_name,
            title="零件风险排行",
            description="按不良和待确认规模排序。",
            rows=[
                (
                    item.part_name,
                    item.part_code,
                    item.total_count,
                    item.bad_count,
                    item.uncertain_count,
                    item.pass_rate,
                )
                for item in overview.part_quality_ranking
            ],
            x=20,
            y=second_row_top,
            width=270,
            height=260,
            accent_color=self.theme.red,
        )
        self._draw_ranking_rows(
            canvas_obj=canvas_obj,
            colors=colors,
            font_name=font_name,
            title="设备风险排行",
            description="判断异常是否更偏向设备侧。",
            rows=[
                (
                    item.device_name,
                    item.device_code,
                    item.total_count,
                    item.bad_count,
                    item.uncertain_count,
                    item.pass_rate,
                )
                for item in overview.device_quality_ranking
            ],
            x=305,
            y=second_row_top,
            width=270,
            height=260,
            accent_color=self.theme.blue,
        )
        self._draw_footer(
            canvas_obj=canvas_obj,
            page_width=page_width,
            font_name=font_name,
            page_number=1,
        )

        canvas_obj.showPage()
        self._draw_page_background(
            canvas_obj=canvas_obj,
            page_width=page_width,
            page_height=page_height,
        )
        self._draw_supporting_summary_page(
            canvas_obj=canvas_obj,
            pdfmetrics=reportlab_modules["pdfmetrics"],
            font_name=font_name,
            page_width=page_width,
            page_height=page_height,
            overview=overview,
        )
        self._draw_footer(
            canvas_obj=canvas_obj,
            page_width=page_width,
            font_name=font_name,
            page_number=2,
        )

        next_page_number = self._draw_ai_analysis_pages(
            canvas_obj=canvas_obj,
            pdfmetrics=reportlab_modules["pdfmetrics"],
            font_name=font_name,
            page_width=page_width,
            page_height=page_height,
            ai_analysis=ai_analysis,
            start_page_number=3,
        )
        next_page_number = self._draw_ai_conversation_pages(
            canvas_obj=canvas_obj,
            colors=colors,
            pdfmetrics=reportlab_modules["pdfmetrics"],
            font_name=font_name,
            page_width=page_width,
            page_height=page_height,
            ai_conversation=ai_conversation or [],
            start_page_number=next_page_number,
        )
        self._draw_sample_image_pages(
            canvas_obj=canvas_obj,
            colors=colors,
            image_reader_cls=reportlab_modules["ImageReader"],
            font_name=font_name,
            page_width=page_width,
            page_height=page_height,
            sample_images=sample_images or [],
            start_page_number=next_page_number,
        )

        canvas_obj.save()
        pdf_bytes = buffer.getvalue()
        filename = (
            f"statistics-lightweight-report-"
            f"{overview.filters.start_date or 'na'}-"
            f"{overview.filters.end_date or 'na'}.pdf"
        ).replace(":", "-")
        return pdf_bytes, filename
