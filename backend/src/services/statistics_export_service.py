"""统计报表服务端 PDF 导出服务。"""

from __future__ import annotations

import base64
from datetime import date, datetime, time, timezone
from html import escape

from sqlalchemy.orm import Session

from src.core.errors import IntegrationError
from src.core.logging import get_logger
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, FileKind
from src.db.models.file_object import FileObject
from src.integrations.cos_client import CosClient
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.schemas.statistics import (
    StatisticsAIAnalysisRequest,
    StatisticsAIAnalysisResponse,
    StatisticsExportPdfRequest,
    StatisticsOverviewResponse,
)
from src.services.statistics_lightweight_pdf_renderer import StatisticsLightweightPdfRenderer
from src.services.statistics_service import StatisticsService

logger = get_logger(__name__)


class StatisticsExportService:
    """负责把统计页概览导出成服务端生成的 PDF 报表。"""

    _sample_file_priority = {
        FileKind.THUMBNAIL: 0,
        FileKind.ANNOTATED: 1,
        FileKind.SOURCE: 2,
    }
    _max_embedded_image_bytes = 2 * 1024 * 1024

    def __init__(self, db: Session) -> None:
        """初始化导出服务依赖。"""

        self.db = db
        self.statistics_service = StatisticsService(db)
        self.record_repository = DetectionRecordRepository(db)
        self.cos_client = CosClient()

    def _format_datetime(self, value: datetime | None) -> str:
        """把时间格式化成报表可直接展示的文本。"""

        if value is None:
            return "未生成"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _format_date(self, value: date | None) -> str:
        """把日期格式化成报表范围文本。"""

        if value is None:
            return "未限定"
        return value.isoformat()

    def _format_percent(self, value: float) -> str:
        """把 0-1 比例转换为百分比文本。"""

        return f"{round(value * 100, 1)}%"

    def _result_label(self, result: DetectionResult) -> str:
        """把最终结果枚举转换为中文标签。"""

        if result == DetectionResult.GOOD:
            return "良品"
        if result == DetectionResult.BAD:
            return "不良"
        return "待确认"

    def _result_color(self, result: DetectionResult) -> str:
        """为不同结果提供统一颜色。"""

        if result == DetectionResult.GOOD:
            return "#37c787"
        if result == DetectionResult.BAD:
            return "#f06565"
        return "#f2b84b"

    def _to_datetime_range(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        """把统计日期窗口转换成仓储查询使用的 UTC 时间范围。"""

        if start_date is None and end_date is None:
            return None, None

        start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc) if start_date else None
        end_at = datetime.combine(end_date, time.max, tzinfo=timezone.utc) if end_date else None
        return start_at, end_at

    def _select_sample_file(self, *, record: DetectionRecord) -> FileObject | None:
        """从单条记录里挑选最适合展示的样本图。"""

        if not record.files:
            return None

        return sorted(
            record.files,
            key=lambda item: (
                self._sample_file_priority.get(item.file_kind, 99),
                -(item.uploaded_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
                -item.id,
            ),
        )[0]

    def _pick_sample_records(
        self,
        *,
        records: list[DetectionRecord],
        limit: int,
    ) -> list[DetectionRecord]:
        """按风险优先级为导出报表挑选若干代表性样本。"""

        if limit <= 0:
            return []

        risky_records = [record for record in records if self._select_sample_file(record=record) is not None]
        risky_records.sort(
            key=lambda record: (
                0 if record.effective_result == DetectionResult.BAD else 1 if record.effective_result == DetectionResult.UNCERTAIN else 2,
                -(record.captured_at or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
                -record.id,
            ),
        )
        return risky_records[:limit]

    def _build_sample_image_entry(self, *, record: DetectionRecord) -> dict[str, str]:
        """把一条代表性记录转换成报表内嵌图片条目。"""

        file_object = self._select_sample_file(record=record)
        if file_object is None:
            return {
                "record_no": record.record_no,
                "title": f"{record.part.name} / {record.device.name}",
                "result_label": self._result_label(record.effective_result),
                "result_color": self._result_color(record.effective_result),
                "defect_text": record.defect_type or record.defect_desc or "未记录缺陷信息",
                "captured_at": self._format_datetime(record.captured_at),
                "image_src": "",
                "image_status": "missing",
                "image_message": "当前记录没有可用图片对象。",
            }

        try:
            file_payload = self.cos_client.read_file_bytes(
                bucket_name=file_object.bucket_name,
                region=file_object.region,
                object_key=file_object.object_key,
                timeout_seconds=60,
                max_bytes=self._max_embedded_image_bytes,
            )
            content_type = str(file_payload["content_type"])
            if not content_type.startswith("image/"):
                raise IntegrationError(
                    code="cos_object_not_image",
                    message="当前样本文件不是可嵌入 PDF 的图像类型。",
                )

            image_src = (
                f"data:{content_type};base64,"
                f"{base64.b64encode(bytes(file_payload['data'])).decode('utf-8')}"
            )
            image_status = "loaded"
            image_message = ""
        except IntegrationError as exc:
            logger.warning(
                "statistics.export_pdf.sample_image_failed event=statistics.export_pdf.sample_image_failed record_id=%s object_key=%s error=%s",
                record.id,
                file_object.object_key,
                exc.message,
            )
            image_src = ""
            image_status = "failed"
            image_message = exc.message

        return {
            "record_no": record.record_no,
            "title": f"{record.part.name} / {record.device.name}",
            "result_label": self._result_label(record.effective_result),
            "result_color": self._result_color(record.effective_result),
            "defect_text": record.defect_type or record.defect_desc or "未记录缺陷信息",
            "captured_at": self._format_datetime(record.captured_at),
            "image_src": image_src,
            "image_status": image_status,
            "image_message": image_message,
        }

    def _load_sample_images(
        self,
        *,
        overview: StatisticsOverviewResponse,
        sample_image_limit: int,
    ) -> list[dict[str, str]]:
        """按当前统计窗口加载报表样本图片。"""

        captured_from, captured_to = self._to_datetime_range(
            start_date=overview.filters.start_date,
            end_date=overview.filters.end_date,
        )
        records = self.record_repository.list_for_statistics(
            part_id=overview.filters.part_id,
            device_id=overview.filters.device_id,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        return [
            self._build_sample_image_entry(record=record)
            for record in self._pick_sample_records(records=records, limit=sample_image_limit)
        ]

    def _build_cached_ai_analysis(
        self,
        *,
        payload: StatisticsExportPdfRequest,
    ) -> StatisticsAIAnalysisResponse | None:
        """把前端已经拿到的 AI 分析文本复用到导出流程中。

        这样用户在页面上已经跑过一次 AI 分析时，PDF 导出不会再重复请求模型，
        可以显著降低导出等待时间，也避免服务端在同一时间既跑 AI 又跑 WeasyPrint。
        """

        cached_answer = (payload.cached_ai_answer or "").strip()
        if not cached_answer:
            return None

        return StatisticsAIAnalysisResponse(
            status="completed",
            answer=cached_answer,
            provider_hint=payload.cached_ai_provider_hint or payload.provider_hint,
            generated_at=payload.cached_ai_generated_at or datetime.now(timezone.utc),
        )

    def _build_trend_svg(self, *, overview: StatisticsOverviewResponse) -> str:
        """生成趋势曲线的内联 SVG。"""

        items = overview.daily_trend
        if not items:
            return "<div class='empty-card'>当前窗口没有趋势数据。</div>"

        width = 720
        height = 260
        left = 52
        top = 20
        right = 20
        bottom = 42
        chart_width = width - left - right
        chart_height = height - top - bottom
        max_value = max([item.total_count for item in items] + [1])

        def build_points(value_attr: str) -> str:
            points: list[str] = []
            for index, item in enumerate(items):
                x = left + chart_width * (0.5 if len(items) == 1 else index / (len(items) - 1))
                y = top + chart_height - chart_height * (getattr(item, value_attr) / max_value)
                points.append(f"{x:.1f},{y:.1f}")
            return " ".join(points)

        labels = "".join(
            [
                (
                    f"<text x='{left + chart_width * (0.5 if len(items) == 1 else index / (len(items) - 1)):.1f}' "
                    f"y='{height - 14}' text-anchor='middle' fill='#708299' font-size='11'>{escape(item.date.strftime('%m-%d'))}</text>"
                )
                for index, item in enumerate(items)
            ]
        )

        return f"""
        <svg viewBox="0 0 {width} {height}" class="report-trend-svg" xmlns="http://www.w3.org/2000/svg">
          <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#d8e3ef" />
          <line x1="{left}" y1="{top + chart_height / 2:.1f}" x2="{width - right}" y2="{top + chart_height / 2:.1f}" stroke="#eaf0f6" stroke-dasharray="6 6" />
          <line x1="{left}" y1="{top + chart_height / 4:.1f}" x2="{width - right}" y2="{top + chart_height / 4:.1f}" stroke="#eaf0f6" stroke-dasharray="6 6" />
          <polyline fill="none" stroke="#1da890" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="{build_points('total_count')}" />
          <polyline fill="none" stroke="#f06565" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="{build_points('bad_count')}" />
          <polyline fill="none" stroke="#f2b84b" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="{build_points('uncertain_count')}" />
          {labels}
        </svg>
        """

    def _build_defect_svg(self, *, overview: StatisticsOverviewResponse) -> str:
        """生成缺陷分布柱状图的内联 SVG。"""

        items = overview.defect_distribution[:6]
        if not items:
            return "<div class='empty-card'>当前窗口没有缺陷分布数据。</div>"

        width = 720
        row_height = 50
        height = 40 + len(items) * row_height
        max_count = max([item.count for item in items] + [1])
        rows = []
        for index, item in enumerate(items):
            row_y = 24 + index * row_height
            bar_width = 420 * (item.count / max_count)
            rows.append(
                f"""
                <text x="0" y="{row_y}" fill="#122133" font-size="14" font-weight="700">{escape(item.defect_type)}</text>
                <text x="620" y="{row_y}" fill="#1da890" font-size="14" text-anchor="end">{item.count}</text>
                <rect x="0" y="{row_y + 10}" width="620" height="10" rx="5" fill="#eaf0f6" />
                <rect x="0" y="{row_y + 10}" width="{bar_width:.1f}" height="10" rx="5" fill="#1da890" />
                """
            )
        return (
            f"<svg viewBox='0 0 {width} {height}' class='report-bar-svg' xmlns='http://www.w3.org/2000/svg'>"
            f"{''.join(rows)}</svg>"
        )

    def _build_distribution_badges(self, *, overview: StatisticsOverviewResponse) -> str:
        """构造结果分布和审核状态分布的摘要徽标。"""

        result_items = "".join(
            [
                (
                    f"<span class='badge' style='border-left:4px solid {self._result_color(item.result)};'>"
                    f"{escape(self._result_label(item.result))} {item.count}</span>"
                )
                for item in overview.result_distribution
            ]
        )
        review_items = "".join(
            [
                (
                    f"<span class='badge badge--review'>"
                    f"{escape(item.review_status.value)} {item.count}</span>"
                )
                for item in overview.review_status_distribution
            ]
        )
        return (
            "<div class='badge-group'>"
            f"<div><h4>结果结构</h4><div class='badge-row'>{result_items}</div></div>"
            f"<div><h4>审核结构</h4><div class='badge-row'>{review_items}</div></div>"
            "</div>"
        )

    def _build_ranking_rows(
        self,
        *,
        items: list[dict[str, str | int | float]],
        max_value: int,
    ) -> str:
        """生成排行条目 HTML。"""

        if not items:
            return "<div class='empty-card'>当前窗口没有排行数据。</div>"

        rows: list[str] = []
        for item in items:
            risk_value = int(item["risk_value"])
            width_percent = max((risk_value / max(max_value, 1)) * 100, 4)
            rows.append(
                f"""
                <article class="ranking-row">
                  <div class="ranking-row__meta">
                    <div>
                      <strong>{escape(str(item['title']))}</strong>
                      <p>{escape(str(item['subtitle']))}</p>
                    </div>
                    <div class="ranking-row__summary">
                      <span>总量 {item['total_count']}</span>
                      <span>不良 {item['bad_count']}</span>
                      <span>待确认 {item['uncertain_count']}</span>
                      <span>良率 {self._format_percent(float(item['pass_rate']))}</span>
                    </div>
                  </div>
                  <div class="ranking-row__track">
                    <div class="ranking-row__fill" style="width:{width_percent:.1f}%"></div>
                  </div>
                </article>
                """
            )
        return "".join(rows)

    def _build_scope_text(self, *, overview: StatisticsOverviewResponse) -> str:
        """把当前统计过滤条件整合成报表副标题。"""

        scope_parts = [
            f"时间范围：{self._format_date(overview.filters.start_date)} 至 {self._format_date(overview.filters.end_date)}",
            f"窗口天数：{overview.filters.days} 天",
        ]
        if overview.filters.part_id is not None:
            scope_parts.append(f"零件 ID：{overview.filters.part_id}")
        if overview.filters.device_id is not None:
            scope_parts.append(f"设备 ID：{overview.filters.device_id}")
        return " | ".join(scope_parts)

    def _build_html(
        self,
        *,
        overview: StatisticsOverviewResponse,
        ai_analysis: StatisticsAIAnalysisResponse | None,
        sample_images: list[dict[str, str]],
    ) -> str:
        """构造服务端 PDF 渲染所需的完整 HTML。"""

        part_rows = self._build_ranking_rows(
            items=[
                {
                    "title": item.part_name,
                    "subtitle": item.part_code,
                    "total_count": item.total_count,
                    "bad_count": item.bad_count,
                    "uncertain_count": item.uncertain_count,
                    "pass_rate": item.pass_rate,
                    "risk_value": item.bad_count + item.uncertain_count,
                }
                for item in overview.part_quality_ranking
            ],
            max_value=max([item.bad_count + item.uncertain_count for item in overview.part_quality_ranking] + [1]),
        )
        device_rows = self._build_ranking_rows(
            items=[
                {
                    "title": item.device_name,
                    "subtitle": item.device_code,
                    "total_count": item.total_count,
                    "bad_count": item.bad_count,
                    "uncertain_count": item.uncertain_count,
                    "pass_rate": item.pass_rate,
                    "risk_value": item.bad_count + item.uncertain_count,
                }
                for item in overview.device_quality_ranking
            ],
            max_value=max([item.bad_count + item.uncertain_count for item in overview.device_quality_ranking] + [1]),
        )
        key_findings_html = "".join(
            [
                f"<li>{escape(item)}</li>"
                for item in overview.key_findings
            ]
        ) or "<li>当前没有可提炼的关键发现。</li>"
        sample_images_html = "".join(
            [
                (
                    f"""
                    <article class="sample-card">
                      <div class="sample-card__header">
                        <strong>{escape(item['record_no'])}</strong>
                        <span style="color:{escape(item['result_color'])}">{escape(item['result_label'])}</span>
                      </div>
                      <div class="sample-card__meta">{escape(item['title'])}</div>
                      <div class="sample-card__meta">缺陷信息：{escape(item['defect_text'])}</div>
                      <div class="sample-card__meta">采集时间：{escape(item['captured_at'])}</div>
                      {
                        f"<img src='{item['image_src']}' alt='{escape(item['record_no'])}' class='sample-card__image' />"
                        if item["image_src"]
                        else f"<div class='sample-card__empty'>{escape(item['image_message'])}</div>"
                      }
                    </article>
                    """
                )
                for item in sample_images
            ]
        ) or "<div class='empty-card'>当前筛选窗口没有可嵌入的 COS 样本图片。</div>"
        ai_text = escape(ai_analysis.answer if ai_analysis is not None else "本次导出未包含 AI 批次分析。")
        ai_meta = (
            f"模型：{escape(ai_analysis.provider_hint or '未生成')} | 时间：{escape(self._format_datetime(ai_analysis.generated_at))}"
            if ai_analysis is not None
            else "模型：未生成"
        )

        return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <style>
      @page {{
        size: A4;
        margin: 10mm;
      }}
      body {{
        margin: 0;
        color: #10233a;
        font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
        font-size: 13px;
        background: #ffffff;
      }}
      .report-shell {{
        display: grid;
        gap: 14px;
      }}
      .hero {{
        padding: 24px;
        border-radius: 18px;
        background: linear-gradient(135deg, #0c1a2f 0%, #102540 100%);
        color: #f8fbff;
      }}
      .hero__eyebrow {{
        color: #7fe4d0;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
      }}
      .hero h1 {{
        margin: 10px 0 8px;
        font-size: 28px;
      }}
      .hero p {{
        margin: 0;
        line-height: 1.7;
        color: #c7d6e6;
      }}
      .summary-grid,
      .panel-grid,
      .ranking-grid,
      .sample-grid {{
        display: grid;
        gap: 12px;
      }}
      .summary-grid {{
        grid-template-columns: repeat(4, 1fr);
      }}
      .panel-grid,
      .ranking-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
      .sample-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
      .card,
      .panel,
      .ai-panel {{
        border: 1px solid #dbe5f0;
        border-radius: 16px;
        background: #ffffff;
        padding: 16px 18px;
      }}
      .card h3,
      .panel h3,
      .ai-panel h3,
      .panel h4 {{
        margin: 0 0 8px;
      }}
      .metric {{
        font-size: 30px;
        font-weight: 700;
        margin: 10px 0 6px;
      }}
      .muted {{
        color: #6f8298;
      }}
      .badge-group {{
        display: grid;
        gap: 10px;
      }}
      .badge-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .badge {{
        display: inline-flex;
        align-items: center;
        padding: 6px 12px;
        border-radius: 999px;
        background: #eef4f8;
        color: #10233a;
        border: 1px solid #d7e3ee;
      }}
      .badge--review {{
        --badge-color: #6aa7ff;
      }}
      .report-trend-svg,
      .report-bar-svg {{
        width: 100%;
        height: auto;
        display: block;
      }}
      .ranking-row {{
        display: grid;
        gap: 8px;
        padding: 10px 0;
        border-bottom: 1px solid #eef3f8;
      }}
      .ranking-row:last-child {{
        border-bottom: none;
      }}
      .ranking-row__meta {{
        display: flex;
        justify-content: space-between;
        gap: 10px;
      }}
      .ranking-row__meta p {{
        margin: 4px 0 0;
        color: #6f8298;
      }}
      .ranking-row__summary {{
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
        color: #6f8298;
        font-size: 12px;
      }}
      .ranking-row__track {{
        height: 8px;
        border-radius: 999px;
        background: #edf2f7;
        overflow: hidden;
      }}
      .ranking-row__fill {{
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, #f06565, #f2b84b);
      }}
      ul {{
        margin: 0;
        padding-left: 20px;
        line-height: 1.8;
      }}
      .ai-panel__meta {{
        color: #6f8298;
        margin-bottom: 12px;
      }}
      .ai-panel__body {{
        white-space: pre-wrap;
        line-height: 1.85;
      }}
      .sample-card {{
        border: 1px solid #dbe5f0;
        border-radius: 14px;
        padding: 12px;
      }}
      .sample-card__header {{
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 8px;
      }}
      .sample-card__meta {{
        color: #6f8298;
        margin-bottom: 6px;
        line-height: 1.6;
      }}
      .sample-card__image {{
        width: 100%;
        max-height: 260px;
        object-fit: contain;
        border: 1px solid #edf2f7;
        border-radius: 10px;
        background: #fafcff;
      }}
      .sample-card__empty,
      .empty-card {{
        display: grid;
        place-content: center;
        min-height: 120px;
        color: #6f8298;
        text-align: center;
        border: 1px dashed #dbe5f0;
        border-radius: 12px;
        background: #fafcff;
      }}
    </style>
  </head>
  <body>
    <div class="report-shell">
      <section class="hero">
        <div class="hero__eyebrow">Statistics Report</div>
        <h1>产品批次统计分析报告</h1>
        <p>{escape(self._build_scope_text(overview=overview))}</p>
        <p>生成时间：{escape(self._format_datetime(overview.generated_at))}</p>
      </section>

      <section class="summary-grid">
        <article class="card">
          <h3>总检测量</h3>
          <div class="metric">{overview.summary.total_count}</div>
          <div class="muted">当前统计窗口内的记录总数</div>
        </article>
        <article class="card">
          <h3>当前良率</h3>
          <div class="metric">{self._format_percent(overview.summary.pass_rate)}</div>
          <div class="muted">良品 {overview.summary.good_count} / 不良 {overview.summary.bad_count}</div>
        </article>
        <article class="card">
          <h3>待确认</h3>
          <div class="metric">{overview.summary.uncertain_count}</div>
          <div class="muted">仍需结合人工复核或补证据确认</div>
        </article>
        <article class="card">
          <h3>待审核</h3>
          <div class="metric">{overview.summary.pending_review_count}</div>
          <div class="muted">已审核 {overview.summary.reviewed_count} 条</div>
        </article>
      </section>

      <section class="panel-grid">
        <article class="panel">
          <h3>趋势曲线</h3>
          <p class="muted">总量、不良和待确认按天变化</p>
          {self._build_trend_svg(overview=overview)}
        </article>
        <article class="panel">
          <h3>缺陷分布与结构摘要</h3>
          <p class="muted">缺陷集中度、结果结构和审核结构</p>
          {self._build_defect_svg(overview=overview)}
          {self._build_distribution_badges(overview=overview)}
        </article>
      </section>

      <section class="ranking-grid">
        <article class="panel">
          <h3>零件风险排行</h3>
          <p class="muted">帮助判断问题是否集中在某些零件批次</p>
          {part_rows}
        </article>
        <article class="panel">
          <h3>设备风险排行</h3>
          <p class="muted">帮助判断问题是否集中在设备链路</p>
          {device_rows}
        </article>
      </section>

      <section class="panel">
        <h3>关键发现</h3>
        <ul>{key_findings_html}</ul>
      </section>

      <section class="ai-panel">
        <h3>AI 批次分析</h3>
        <div class="ai-panel__meta">{escape(ai_meta)}</div>
        <div class="ai-panel__body">{ai_text}</div>
      </section>

      <section class="panel">
        <h3>COS 样本图像</h3>
        <p class="muted">本节由服务端直接通过 COS 连接抽样读取代表图片并嵌入 PDF，优先使用缩略图以控制导出耗时和 CPU 占用。</p>
        <div class="sample-grid">{sample_images_html}</div>
      </section>
    </div>
  </body>
</html>"""

    def _build_ai_analysis(
        self,
        *,
        payload: StatisticsExportPdfRequest,
    ) -> StatisticsAIAnalysisResponse | None:
        """按需生成或复用统计 AI 分析文本。"""

        if not payload.include_ai_analysis:
            return None

        cached_ai_analysis = self._build_cached_ai_analysis(payload=payload)
        if cached_ai_analysis is not None:
            return cached_ai_analysis

        try:
            return self.statistics_service.request_ai_analysis(
                StatisticsAIAnalysisRequest(
                    model_profile_id=payload.model_profile_id,
                    provider_hint=payload.provider_hint,
                    note=payload.note,
                    start_date=payload.start_date,
                    end_date=payload.end_date,
                    days=payload.days,
                    part_id=payload.part_id,
                    device_id=payload.device_id,
                )
            )
        except Exception as exc:
            logger.warning(
                "statistics.export_pdf.ai_analysis_failed event=statistics.export_pdf.ai_analysis_failed error=%s",
                str(exc),
            )
            return StatisticsAIAnalysisResponse(
                status="failed",
                answer="本次 PDF 导出未能成功生成 AI 批次分析，报表已按纯统计数据模式继续导出。",
                provider_hint=payload.provider_hint,
                generated_at=datetime.now(timezone.utc),
            )

    def build_pdf(self, payload: StatisticsExportPdfRequest) -> tuple[bytes, str]:
        """构造统计报表 PDF 二进制和推荐文件名。"""

        overview = self.statistics_service.get_overview(
            start_date=payload.start_date,
            end_date=payload.end_date,
            days=payload.days,
            part_id=payload.part_id,
            device_id=payload.device_id,
        )
        ai_analysis = self._build_ai_analysis(payload=payload)

        if payload.export_mode == "lightweight":
            # 轻量版走直接绘制链路，不再继续抓 COS 样本图，也不依赖 WeasyPrint。
            return StatisticsLightweightPdfRenderer().build_pdf(
                overview=overview,
                ai_analysis=ai_analysis,
            )

        sample_images = (
            self._load_sample_images(
                overview=overview,
                sample_image_limit=payload.sample_image_limit,
            )
            if payload.include_sample_images and payload.sample_image_limit > 0
            else []
        )
        html_text = self._build_html(
            overview=overview,
            ai_analysis=ai_analysis,
            sample_images=sample_images,
        )

        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise IntegrationError(
                code="pdf_renderer_unavailable",
                message="当前服务端尚未安装 WeasyPrint，暂时无法生成服务端 PDF。",
                details={
                    "hint": "请在服务器安装 weasyprint 及其系统依赖后重试。",
                },
            ) from exc

        try:
            pdf_bytes = HTML(string=html_text).write_pdf()
        except Exception as exc:
            raise IntegrationError(
                code="pdf_export_failed",
                message="服务端 PDF 生成失败，请检查 WeasyPrint、字体和系统依赖配置。",
                details={
                    "reason": str(exc),
                },
            ) from exc

        filename = (
            f"statistics-report-"
            f"{self._format_date(overview.filters.start_date)}-"
            f"{self._format_date(overview.filters.end_date)}.pdf"
        ).replace(":", "-")
        return pdf_bytes, filename
