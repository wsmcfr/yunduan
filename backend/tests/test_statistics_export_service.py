"""统计 PDF 导出服务的关键回归测试。"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.core.errors import IntegrationError
from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.enums import DetectionResult, DeviceStatus, DeviceType, FileKind, ReviewStatus, StorageProvider
from src.db.models.file_object import FileObject
from src.db.models.part import Part
from src.schemas.statistics import (
    DailyTrendItem,
    DefectDistributionItem,
    DeviceQualityItem,
    PartQualityItem,
    ResultDistributionItem,
    ReviewStatusDistributionItem,
    StatisticsAIAnalysisResponse,
    StatisticsExportPdfRequest,
    StatisticsFiltersResponse,
    StatisticsOverviewResponse,
    StatisticsPartImageGroup,
    StatisticsSampleGalleryResponse,
    SummaryStatisticsResponse,
)
from src.services.statistics_export_service import StatisticsExportService
from src.services.statistics_lightweight_pdf_renderer import StatisticsLightweightPdfRenderer


class FakePdfTextObject:
    """模拟 reportlab 文本对象，便于测试分页时的文本写入流程。"""

    def __init__(self) -> None:
        """初始化文本对象状态。"""

        self.lines: list[str] = []

    def setFont(self, font_name: str, font_size: int) -> None:  # noqa: N802
        """兼容 reportlab 的接口，测试里不需要真实排版。"""

    def setLeading(self, leading: int) -> None:  # noqa: N802
        """兼容 reportlab 的接口，测试里只关心是否被调用。"""

    def setFillColor(self, color: str) -> None:  # noqa: N802
        """兼容 reportlab 的接口，测试里不需要真实颜色。"""

    def textLine(self, text: str) -> None:  # noqa: N802
        """记录写入的单行文本。"""

        self.lines.append(text)


class FakePdfCanvas:
    """模拟 reportlab canvas，专门用于验证轻量 PDF 的分页行为。"""

    def __init__(self, buffer, pagesize, pageCompression=1) -> None:  # noqa: N803
        """保存缓冲区和页面统计信息。"""

        self.buffer = buffer
        self.pagesize = pagesize
        self.page_compression = pageCompression
        self.show_page_calls = 0
        self.drawn_strings: list[str] = []

    def setTitle(self, title: str) -> None:  # noqa: N802
        """兼容 reportlab 的标题接口。"""

    def setAuthor(self, author: str) -> None:  # noqa: N802
        """兼容 reportlab 的作者接口。"""

    def setFillColor(self, color: str) -> None:  # noqa: N802
        """兼容 reportlab 的填充色接口。"""

    def rect(self, x: float, y: float, width: float, height: float, fill: int = 0, stroke: int = 1) -> None:
        """兼容矩形绘制接口。"""

    def roundRect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float,
        fill: int = 0,
        stroke: int = 1,
    ) -> None:  # noqa: N802
        """兼容圆角矩形接口。"""

    def setFont(self, font_name: str, font_size: int) -> None:  # noqa: N802
        """兼容字体设置接口。"""

    def drawString(self, x: float, y: float, text: str) -> None:  # noqa: N802
        """记录普通文本绘制内容。"""

        self.drawn_strings.append(text)

    def drawRightString(self, x: float, y: float, text: str) -> None:  # noqa: N802
        """记录右对齐文本绘制内容。"""

        self.drawn_strings.append(text)

    def drawCentredString(self, x: float, y: float, text: str) -> None:  # noqa: N802
        """记录居中文本绘制内容。"""

        self.drawn_strings.append(text)

    def setStrokeColor(self, color: str) -> None:  # noqa: N802
        """兼容描边色接口。"""

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """兼容直线绘制接口。"""

    def setDash(self, *dash_values: int) -> None:  # noqa: N802
        """兼容虚线接口。"""

    def circle(self, x: float, y: float, radius: float, fill: int = 0, stroke: int = 1) -> None:
        """兼容圆形绘制接口。"""

    def setLineWidth(self, width: float) -> None:  # noqa: N802
        """兼容线宽接口。"""

    def beginText(self, x: float, y: float) -> FakePdfTextObject:  # noqa: N802
        """返回假的文本对象。"""

        return FakePdfTextObject()

    def drawText(self, text_object: FakePdfTextObject) -> None:  # noqa: N802
        """把文本对象中的文本也记到画布日志里。"""

        self.drawn_strings.extend(text_object.lines)

    def showPage(self) -> None:  # noqa: N802
        """记录翻页次数。"""

        self.show_page_calls += 1

    def save(self) -> None:
        """写入一个假的 PDF 头，保证返回值可断言。"""

        self.buffer.write(b"%PDF-fake")


class StatisticsExportServiceTestCase(unittest.TestCase):
    """验证 PDF 导出链路里的关键性能兜底逻辑。"""

    def build_service(self) -> StatisticsExportService:
        """创建不依赖真实数据库连接的导出服务实例。"""

        return StatisticsExportService(db=None)

    def build_statistics_overview(self) -> StatisticsOverviewResponse:
        """构造轻量 PDF 渲染测试用的统计概览数据。"""

        now = datetime(2026, 4, 21, 8, 30, 0, tzinfo=timezone.utc)
        return StatisticsOverviewResponse(
            filters=StatisticsFiltersResponse(
                start_date=date(2026, 4, 7),
                end_date=date(2026, 4, 20),
                days=14,
                part_id=None,
                device_id=None,
            ),
            summary=SummaryStatisticsResponse(
                total_count=6,
                good_count=2,
                bad_count=3,
                uncertain_count=1,
                reviewed_count=3,
                pending_review_count=3,
                pass_rate=2 / 6,
            ),
            daily_trend=[
                DailyTrendItem(date=date(2026, 4, 17), total_count=0, good_count=0, bad_count=0, uncertain_count=0),
                DailyTrendItem(date=date(2026, 4, 18), total_count=1, good_count=0, bad_count=1, uncertain_count=0),
                DailyTrendItem(date=date(2026, 4, 19), total_count=2, good_count=1, bad_count=1, uncertain_count=0),
                DailyTrendItem(date=date(2026, 4, 20), total_count=3, good_count=1, bad_count=1, uncertain_count=1),
            ],
            defect_distribution=[
                DefectDistributionItem(defect_type="冲压毛刺", count=2),
                DefectDistributionItem(defect_type="压痕", count=1),
                DefectDistributionItem(defect_type="无明显缺陷", count=1),
            ],
            result_distribution=[
                ResultDistributionItem(result=DetectionResult.GOOD, count=2),
                ResultDistributionItem(result=DetectionResult.BAD, count=3),
                ResultDistributionItem(result=DetectionResult.UNCERTAIN, count=1),
            ],
            review_status_distribution=[
                ReviewStatusDistributionItem(review_status=ReviewStatus.PENDING, count=3),
                ReviewStatusDistributionItem(review_status=ReviewStatus.REVIEWED, count=3),
            ],
            part_quality_ranking=[
                PartQualityItem(
                    part_id=index + 1,
                    part_code=f"PART-{index + 1:03d}",
                    part_name=f"冲压件-{index + 1}",
                    total_count=index + 2,
                    good_count=1,
                    bad_count=1,
                    uncertain_count=index % 2,
                    pass_rate=0.5,
                )
                for index in range(5)
            ],
            device_quality_ranking=[
                DeviceQualityItem(
                    device_id=index + 1,
                    device_code=f"MP157-{index + 1:03d}",
                    device_name=f"主检设备-{index + 1}",
                    total_count=index + 2,
                    good_count=1,
                    bad_count=1,
                    uncertain_count=index % 2,
                    pass_rate=0.5,
                )
                for index in range(5)
            ],
            key_findings=[
                "冲压毛刺是不良记录的主要来源，需要优先复查刀口状态。",
                "最近一天检测总量明显上升，不良与待确认同步增长。",
                "设备 3 的异常占比偏高，建议先核查该机位的治具与光源。",
            ],
            sample_gallery=StatisticsSampleGalleryResponse(
                total_record_count=6,
                total_image_count=9,
                total_part_count=2,
                latest_uploaded_at=now,
                groups=[
                    StatisticsPartImageGroup(
                        part_id=1,
                        part_code="PART-001",
                        part_name="冲压垫片",
                        part_category="冲压件",
                        record_count=4,
                        image_count=6,
                        latest_uploaded_at=now,
                        items=[],
                    ),
                    StatisticsPartImageGroup(
                        part_id=2,
                        part_code="PART-002",
                        part_name="冲压圈件",
                        part_category="冲压件",
                        record_count=2,
                        image_count=3,
                        latest_uploaded_at=now,
                        items=[],
                    ),
                ],
            ),
            generated_at=now,
        )

    def build_fake_reportlab_modules(self) -> tuple[dict[str, object], dict[str, FakePdfCanvas]]:
        """构造假的 reportlab 模块字典，并暴露 canvas 实例给断言使用。"""

        holder: dict[str, FakePdfCanvas] = {}

        def create_canvas(buffer, pagesize, pageCompression=1):  # noqa: N803
            """记录轻量渲染器实际创建的画布实例。"""

            holder["canvas"] = FakePdfCanvas(buffer, pagesize, pageCompression)
            return holder["canvas"]

        fake_pdfmetrics = SimpleNamespace(
            stringWidth=lambda text, font_name, font_size: len(text) * font_size * 0.52,
        )
        modules = {
            "colors": SimpleNamespace(HexColor=lambda value: value),
            "A4": (595.27, 841.89),
            "mm": 1,
            "pdfmetrics": fake_pdfmetrics,
            "UnicodeCIDFont": Mock(),
            "canvas": SimpleNamespace(Canvas=create_canvas),
        }
        return modules, holder

    def build_record_with_files(self) -> DetectionRecord:
        """构造带多种图片类型的检测记录，验证导出时的选图优先级。"""

        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        part = Part(
            id=1,
            part_code="PART-001",
            name="金属垫片",
            category="垫片",
            description=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        device = Device(
            id=1,
            device_code="MP157-001",
            name="MP157 主检设备",
            device_type=DeviceType.MP157,
            status=DeviceStatus.ONLINE,
            firmware_version=None,
            ip_address=None,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        record = DetectionRecord(
            id=1,
            record_no="REC-20260420-0001",
            part_id=1,
            device_id=1,
            result=DetectionResult.BAD,
            review_status=ReviewStatus.PENDING,
            surface_result=None,
            backlight_result=None,
            eddy_result=None,
            defect_type="表面划痕",
            defect_desc="用于测试 PDF 导出选图逻辑。",
            confidence_score=0.98,
            captured_at=now,
            detected_at=now,
            uploaded_at=now,
            storage_last_modified=now,
            created_at=now,
            updated_at=now,
        )
        record.part = part
        record.device = device
        record.files = [
            FileObject(
                id=11,
                detection_record_id=1,
                file_kind=FileKind.SOURCE,
                storage_provider=StorageProvider.COS,
                bucket_name="demo-bucket",
                region="ap-guangzhou",
                object_key="detections/demo/source.png",
                content_type="image/png",
                size_bytes=2048,
                etag=None,
                uploaded_at=now,
                storage_last_modified=now,
                created_at=now,
            ),
            FileObject(
                id=12,
                detection_record_id=1,
                file_kind=FileKind.THUMBNAIL,
                storage_provider=StorageProvider.COS,
                bucket_name="demo-bucket",
                region="ap-guangzhou",
                object_key="detections/demo/thumb.png",
                content_type="image/png",
                size_bytes=512,
                etag=None,
                uploaded_at=now,
                storage_last_modified=now,
                created_at=now,
            ),
            FileObject(
                id=13,
                detection_record_id=1,
                file_kind=FileKind.ANNOTATED,
                storage_provider=StorageProvider.COS,
                bucket_name="demo-bucket",
                region="ap-guangzhou",
                object_key="detections/demo/annotated.png",
                content_type="image/png",
                size_bytes=1024,
                etag=None,
                uploaded_at=now,
                storage_last_modified=now,
                created_at=now,
            ),
        ]
        return record

    def test_select_sample_file_prioritizes_thumbnail_for_pdf_export(self) -> None:
        """验证 PDF 导出优先选缩略图，避免直接把大图嵌进 PDF。"""

        service = self.build_service()
        record = self.build_record_with_files()

        selected_file = service._select_sample_file(record=record)

        self.assertIsNotNone(selected_file)
        self.assertEqual(selected_file.file_kind, FileKind.THUMBNAIL)
        self.assertEqual(selected_file.object_key, "detections/demo/thumb.png")

    def test_build_ai_analysis_reuses_cached_frontend_result(self) -> None:
        """验证当前端已拿到 AI 分析时，PDF 导出不会再次触发模型请求。"""

        service = self.build_service()
        service.statistics_service.request_ai_analysis = Mock(side_effect=AssertionError("不应再次请求 AI"))  # type: ignore[method-assign]
        cached_generated_at = datetime(2026, 4, 20, 13, 30, 0, tzinfo=timezone.utc)
        payload = StatisticsExportPdfRequest(
            model_profile_id=None,
            provider_hint="DeepSeek 官方",
            note=None,
            start_date=None,
            end_date=None,
            days=14,
            part_id=None,
            device_id=None,
            include_ai_analysis=True,
            cached_ai_answer="这是前端已经生成好的批次分析结论。",
            cached_ai_provider_hint="DeepSeek 官方",
            cached_ai_generated_at=cached_generated_at,
            include_sample_images=False,
            sample_image_limit=0,
        )

        ai_analysis = service._build_ai_analysis(payload=payload)

        self.assertIsNotNone(ai_analysis)
        self.assertEqual(ai_analysis.answer, "这是前端已经生成好的批次分析结论。")
        self.assertEqual(ai_analysis.provider_hint, "DeepSeek 官方")
        self.assertEqual(ai_analysis.generated_at, cached_generated_at)
        service.statistics_service.request_ai_analysis.assert_not_called()  # type: ignore[attr-defined]

    @patch("src.services.statistics_export_service.StatisticsLightweightPdfRenderer")
    def test_build_pdf_dispatches_to_lightweight_renderer(
        self,
        lightweight_renderer_cls: Mock,
    ) -> None:
        """验证轻量版导出会切换到直接绘制链路，而不是继续走视觉版渲染。"""

        service = self.build_service()
        fake_overview = Mock(name="overview")
        fake_ai_analysis = Mock(name="ai_analysis")
        service.statistics_service.get_overview = Mock(return_value=fake_overview)  # type: ignore[method-assign]
        service._build_ai_analysis = Mock(return_value=fake_ai_analysis)  # type: ignore[method-assign]
        service._load_sample_images = Mock(side_effect=AssertionError("轻量版不应继续抓取样本图"))  # type: ignore[method-assign]
        renderer_instance = lightweight_renderer_cls.return_value
        renderer_instance.build_pdf.return_value = (b"%PDF-lightweight", "statistics-lightweight-report.pdf")

        payload = StatisticsExportPdfRequest(
            export_mode="lightweight",
            model_profile_id=None,
            provider_hint="DeepSeek 官方",
            note=None,
            start_date=None,
            end_date=None,
            days=14,
            part_id=None,
            device_id=None,
            include_ai_analysis=False,
            include_sample_images=False,
            sample_image_limit=0,
        )

        pdf_bytes, filename = service.build_pdf(payload)

        self.assertEqual(pdf_bytes, b"%PDF-lightweight")
        self.assertEqual(filename, "statistics-lightweight-report.pdf")
        renderer_instance.build_pdf.assert_called_once_with(
            overview=fake_overview,
            ai_analysis=fake_ai_analysis,
        )
        service._load_sample_images.assert_not_called()  # type: ignore[attr-defined]

    def test_lightweight_renderer_reports_missing_reportlab_dependency(self) -> None:
        """验证轻量版渲染器在缺少 reportlab 时能抛出稳定的集成错误。"""

        original_import = __import__

        def fake_import(
            name: str,
            globals=None,
            locals=None,
            fromlist=(),
            level: int = 0,
        ):
            """仅对 reportlab 依赖模拟缺失，其它导入继续走真实导入逻辑。"""

            if name.startswith("reportlab"):
                raise ImportError("mocked reportlab missing")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(IntegrationError) as caught:
                StatisticsLightweightPdfRenderer()._load_reportlab()

        self.assertEqual(caught.exception.code, "lightweight_pdf_renderer_unavailable")

    def test_lightweight_renderer_accepts_registered_font_name_strings(self) -> None:
        """验证已注册字体列表为字符串时，轻量渲染器不会错误访问 `fontName` 属性。"""

        renderer = StatisticsLightweightPdfRenderer()
        pdfmetrics = Mock()
        pdfmetrics.getRegisteredFontNames.return_value = ["Helvetica", "STSong-Light"]
        unicode_cid_font = Mock()

        font_name = renderer._ensure_font_registered(
            pdfmetrics=pdfmetrics,
            unicode_cid_font=unicode_cid_font,
        )

        self.assertEqual(font_name, "STSong-Light")
        pdfmetrics.registerFont.assert_not_called()

    def test_lightweight_renderer_adds_supporting_summary_page_before_finishing(self) -> None:
        """验证轻量版即使不带 AI，也会生成独立的摘要页而不是把内容继续挤在首页。"""

        renderer = StatisticsLightweightPdfRenderer()
        fake_modules, holder = self.build_fake_reportlab_modules()

        with (
            patch.object(renderer, "_load_reportlab", return_value=fake_modules),
            patch.object(renderer, "_ensure_font_registered", return_value="FakeFont"),
        ):
            pdf_bytes, filename = renderer.build_pdf(
                overview=self.build_statistics_overview(),
                ai_analysis=None,
            )

        self.assertEqual(pdf_bytes, b"%PDF-fake")
        self.assertIn("statistics-lightweight-report-", filename)
        self.assertEqual(holder["canvas"].show_page_calls, 1)
        self.assertIn("关键发现与样本摘要", holder["canvas"].drawn_strings)

    def test_lightweight_renderer_places_ai_analysis_after_summary_pages(self) -> None:
        """验证 AI 分析全文会从后续页面开始，而不是挤进首页或摘要页。"""

        renderer = StatisticsLightweightPdfRenderer()
        fake_modules, holder = self.build_fake_reportlab_modules()

        with (
            patch.object(renderer, "_load_reportlab", return_value=fake_modules),
            patch.object(renderer, "_ensure_font_registered", return_value="FakeFont"),
        ):
            renderer.build_pdf(
                overview=self.build_statistics_overview(),
                ai_analysis=StatisticsAIAnalysisResponse(
                    status="completed",
                    answer="这是统计 AI 的简要批次结论，用于验证 AI 页面会在摘要页之后单独生成。",
                    provider_hint="DeepSeek 官方",
                    generated_at=datetime(2026, 4, 21, 9, 0, 0, tzinfo=timezone.utc),
                ),
            )

        self.assertEqual(holder["canvas"].show_page_calls, 2)
        self.assertIn("AI 批次分析全文", holder["canvas"].drawn_strings)
