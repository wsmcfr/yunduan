"""统计服务实现。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterator

from sqlalchemy.orm import Session

from src.core.errors import AppError
from src.core.sse import build_sse_error_payload, format_sse_event
from src.integrations.ai_review_client import AIReviewClient
from src.integrations.cos_client import CosClient
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.schemas.statistics import (
    DailyTrendItem,
    DailyTrendResponse,
    DefectDistributionItem,
    DefectDistributionResponse,
    DeviceQualityItem,
    PartQualityItem,
    ResultDistributionItem,
    ReviewStatusDistributionItem,
    StatisticsAIAnalysisRequest,
    StatisticsAIAnalysisResponse,
    StatisticsFiltersResponse,
    StatisticsPartImageGroup,
    StatisticsSampleGalleryResponse,
    StatisticsSampleImageItem,
    StatisticsOverviewResponse,
    SummaryStatisticsResponse,
)
from src.services.ai_gateway_service import AIGatewayService
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, FileKind, ReviewStatus


class StatisticsService:
    """封装统计页概览、聚合分析与 AI 批次分析流程。"""

    def __init__(self, db: Session) -> None:
        """初始化统计服务依赖。"""

        self.db = db
        self.record_repository = DetectionRecordRepository(db)
        self.ai_review_client = AIReviewClient()
        self.cos_client = CosClient()

    def _to_datetime_range(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        """将按日查询条件转换为 UTC 时间区间。"""

        if start_date is None and end_date is None:
            return None, None

        start_at = (
            datetime.combine(start_date, time.min, tzinfo=timezone.utc) if start_date is not None else None
        )
        end_at = (
            datetime.combine(end_date, time.max, tzinfo=timezone.utc) if end_date is not None else None
        )
        return start_at, end_at

    def _resolve_date_window(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        days: int,
    ) -> tuple[date | None, date | None]:
        """把统计页的相对天数和显式日期区间统一成稳定窗口。"""

        if start_date is None and end_date is None:
            resolved_end_date = datetime.now(timezone.utc).date()
            resolved_start_date = resolved_end_date - timedelta(days=max(days - 1, 0))
            return resolved_start_date, resolved_end_date

        if start_date is None and end_date is not None:
            return end_date - timedelta(days=max(days - 1, 0)), end_date

        if start_date is not None and end_date is None:
            return start_date, start_date + timedelta(days=max(days - 1, 0))

        return start_date, end_date

    def _load_records(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        part_id: int | None = None,
        device_id: int | None = None,
    ) -> list[DetectionRecord]:
        """按过滤条件加载统计计算所需的检测记录集合。"""

        captured_from, captured_to = self._to_datetime_range(start_date=start_date, end_date=end_date)
        return self.record_repository.list_for_statistics(
            part_id=part_id,
            device_id=device_id,
            captured_from=captured_from,
            captured_to=captured_to,
        )

    def _resolve_result(self, record: DetectionRecord) -> DetectionResult:
        """解析统计时应采用的最终生效结果。"""

        return record.effective_result

    def _build_summary_from_records(self, *, records: list[DetectionRecord]) -> SummaryStatisticsResponse:
        """根据记录集合构造概览统计。"""

        counter = Counter(self._resolve_result(record) for record in records)
        reviewed_count = sum(1 for record in records if record.latest_review is not None)
        total_count = len(records)
        good_count = counter[DetectionResult.GOOD]
        bad_count = counter[DetectionResult.BAD]
        uncertain_count = counter[DetectionResult.UNCERTAIN]
        pass_rate = round((good_count / total_count) if total_count else 0.0, 4)

        return SummaryStatisticsResponse(
            total_count=total_count,
            good_count=good_count,
            bad_count=bad_count,
            uncertain_count=uncertain_count,
            reviewed_count=reviewed_count,
            pending_review_count=max(total_count - reviewed_count, 0),
            pass_rate=pass_rate,
        )

    def _build_daily_trend_from_records(
        self,
        *,
        records: list[DetectionRecord],
        start_date: date | None,
        end_date: date | None,
    ) -> list[DailyTrendItem]:
        """根据记录集合构造按天趋势数据。"""

        if start_date is None or end_date is None:
            return []

        bucket: dict[date, Counter[str]] = defaultdict(Counter)
        for record in records:
            bucket_date = record.captured_at.astimezone(timezone.utc).date()
            bucket[bucket_date]["total"] += 1
            bucket[bucket_date][self._resolve_result(record).value] += 1

        items: list[DailyTrendItem] = []
        cursor = start_date
        while cursor <= end_date:
            counter = bucket[cursor]
            items.append(
                DailyTrendItem(
                    date=cursor,
                    total_count=counter.get("total", 0),
                    good_count=counter.get(DetectionResult.GOOD.value, 0),
                    bad_count=counter.get(DetectionResult.BAD.value, 0),
                    uncertain_count=counter.get(DetectionResult.UNCERTAIN.value, 0),
                )
            )
            cursor += timedelta(days=1)

        return items

    def _build_defect_distribution_from_records(
        self,
        *,
        records: list[DetectionRecord],
    ) -> list[DefectDistributionItem]:
        """根据记录集合构造缺陷类型分布。"""

        counter: Counter[str] = Counter()
        for record in records:
            latest_review = record.latest_review
            defect_type = None
            if latest_review is not None and latest_review.defect_type:
                defect_type = latest_review.defect_type
            elif record.defect_type:
                defect_type = record.defect_type

            if defect_type:
                counter[defect_type] += 1

        return [
            DefectDistributionItem(defect_type=defect_type, count=count)
            for defect_type, count in counter.most_common()
        ]

    def _build_result_distribution_from_records(
        self,
        *,
        records: list[DetectionRecord],
    ) -> list[ResultDistributionItem]:
        """构造最终结果分布。"""

        counter = Counter(self._resolve_result(record) for record in records)
        return [
            ResultDistributionItem(result=result, count=counter.get(result, 0))
            for result in DetectionResult
        ]

    def _build_review_status_distribution_from_records(
        self,
        *,
        records: list[DetectionRecord],
    ) -> list[ReviewStatusDistributionItem]:
        """构造审核状态分布。"""

        counter = Counter(record.review_status for record in records)
        return [
            ReviewStatusDistributionItem(review_status=review_status, count=counter.get(review_status, 0))
            for review_status in ReviewStatus
        ]

    def _build_part_quality_ranking(
        self,
        *,
        records: list[DetectionRecord],
    ) -> list[PartQualityItem]:
        """构造按零件维度聚合的质量排行。"""

        bucket: dict[int, dict[str, Any]] = {}
        for record in records:
            part_state = bucket.setdefault(
                record.part_id,
                {
                    "part_id": record.part_id,
                    "part_code": record.part.part_code,
                    "part_name": record.part.name,
                    "total_count": 0,
                    "good_count": 0,
                    "bad_count": 0,
                    "uncertain_count": 0,
                },
            )
            part_state["total_count"] += 1
            resolved_result = self._resolve_result(record)
            if resolved_result == DetectionResult.GOOD:
                part_state["good_count"] += 1
            elif resolved_result == DetectionResult.BAD:
                part_state["bad_count"] += 1
            else:
                part_state["uncertain_count"] += 1

        items = [
            PartQualityItem(
                part_id=item["part_id"],
                part_code=item["part_code"],
                part_name=item["part_name"],
                total_count=item["total_count"],
                good_count=item["good_count"],
                bad_count=item["bad_count"],
                uncertain_count=item["uncertain_count"],
                pass_rate=round(
                    (item["good_count"] / item["total_count"]) if item["total_count"] else 0.0,
                    4,
                ),
            )
            for item in bucket.values()
        ]
        return sorted(
            items,
            key=lambda item: (
                -item.bad_count,
                -item.uncertain_count,
                -item.total_count,
                item.pass_rate,
                item.part_code,
            ),
        )[:8]

    def _build_device_quality_ranking(
        self,
        *,
        records: list[DetectionRecord],
    ) -> list[DeviceQualityItem]:
        """构造按设备维度聚合的质量排行。"""

        bucket: dict[int, dict[str, Any]] = {}
        for record in records:
            device_state = bucket.setdefault(
                record.device_id,
                {
                    "device_id": record.device_id,
                    "device_code": record.device.device_code,
                    "device_name": record.device.name,
                    "total_count": 0,
                    "good_count": 0,
                    "bad_count": 0,
                    "uncertain_count": 0,
                },
            )
            device_state["total_count"] += 1
            resolved_result = self._resolve_result(record)
            if resolved_result == DetectionResult.GOOD:
                device_state["good_count"] += 1
            elif resolved_result == DetectionResult.BAD:
                device_state["bad_count"] += 1
            else:
                device_state["uncertain_count"] += 1

        items = [
            DeviceQualityItem(
                device_id=item["device_id"],
                device_code=item["device_code"],
                device_name=item["device_name"],
                total_count=item["total_count"],
                good_count=item["good_count"],
                bad_count=item["bad_count"],
                uncertain_count=item["uncertain_count"],
                pass_rate=round(
                    (item["good_count"] / item["total_count"]) if item["total_count"] else 0.0,
                    4,
                ),
            )
            for item in bucket.values()
        ]
        return sorted(
            items,
            key=lambda item: (
                -item.bad_count,
                -item.uncertain_count,
                -item.total_count,
                item.pass_rate,
                item.device_code,
            ),
        )[:8]

    def _build_key_findings(
        self,
        *,
        filters: StatisticsFiltersResponse,
        summary: SummaryStatisticsResponse,
        daily_trend: list[DailyTrendItem],
        defect_distribution: list[DefectDistributionItem],
        part_quality_ranking: list[PartQualityItem],
        device_quality_ranking: list[DeviceQualityItem],
    ) -> list[str]:
        """提炼一组可直接展示或喂给 AI 的结构化结论。"""

        if summary.total_count == 0:
            return ["当前筛选条件下没有检测记录，无法形成有效统计结论。"]

        findings = [
            (
                f"当前统计窗口共覆盖 {summary.total_count} 条记录，良率约为 "
                f"{round(summary.pass_rate * 100, 1)}%，不良 {summary.bad_count} 条，待确认 {summary.uncertain_count} 条。"
            )
        ]

        if summary.pending_review_count > 0:
            pending_ratio = round((summary.pending_review_count / summary.total_count) * 100, 1)
            findings.append(
                f"当前仍有 {summary.pending_review_count} 条待人工复核，约占总量的 {pending_ratio}%。"
            )

        peak_bad_day = max(daily_trend, key=lambda item: item.bad_count, default=None)
        if peak_bad_day is not None and peak_bad_day.bad_count > 0:
            findings.append(
                f"不良峰值出现在 {peak_bad_day.date}，当日不良数量为 {peak_bad_day.bad_count} 条。"
            )

        if defect_distribution:
            top_defect = defect_distribution[0]
            findings.append(
                f"缺陷分布中占比最高的是“{top_defect.defect_type}”，累计 {top_defect.count} 条。"
            )

        if part_quality_ranking:
            top_part = part_quality_ranking[0]
            findings.append(
                (
                    f"零件维度风险最高的是 {top_part.part_name}（{top_part.part_code}），"
                    f"总量 {top_part.total_count}，不良 {top_part.bad_count}，待确认 {top_part.uncertain_count}。"
                )
            )

        if device_quality_ranking:
            top_device = device_quality_ranking[0]
            findings.append(
                (
                    f"设备维度需重点关注 {top_device.device_name}（{top_device.device_code}），"
                    f"总量 {top_device.total_count}，不良 {top_device.bad_count}，待确认 {top_device.uncertain_count}。"
                )
            )

        if filters.part_id is not None or filters.device_id is not None:
            findings.append(
                "当前结果已带筛选条件，AI 解读时应优先理解为“局部批次表现”，而不是全局产线结论。"
            )

        return findings[:6]

    def _sample_file_priority(self, *, file_kind: FileKind) -> int:
        """返回统计图库预览图的优先级。"""

        if file_kind == FileKind.ANNOTATED:
            return 0
        if file_kind == FileKind.SOURCE:
            return 1
        if file_kind == FileKind.THUMBNAIL:
            return 2
        return 99

    def _build_file_preview_url(self, *, bucket_name: str, region: str, object_key: str) -> str | None:
        """为统计页图库里的样本图生成可访问地址。"""

        return self.cos_client.build_object_access_url(
            bucket_name=bucket_name,
            region=region,
            object_key=object_key,
        )

    def _select_sample_file(self, *, record: DetectionRecord):
        """从单条检测记录中挑一张最适合统计页展示的主图。"""

        image_files = [
            file_object
            for file_object in record.files
            if file_object.file_kind in {FileKind.ANNOTATED, FileKind.SOURCE, FileKind.THUMBNAIL}
        ]
        if not image_files:
            return None

        return sorted(
            image_files,
            key=lambda item: (
                self._sample_file_priority(file_kind=item.file_kind),
                -(
                    (
                        item.uploaded_at
                        or item.storage_last_modified
                        or item.created_at
                    ).timestamp()
                ),
                -item.id,
            ),
        )[0]

    def _build_sample_gallery(
        self,
        *,
        records: list[DetectionRecord],
    ) -> StatisticsSampleGalleryResponse:
        """构造统计页图库摘要。

        当前先保证统计接口可稳定返回图库区域所需的最小可用结构，
        这样统计页、导出和 AI 分析不会因为半改 schema 而直接失败。
        """

        group_bucket: dict[int, dict[str, Any]] = {}
        total_image_count = 0
        latest_uploaded_at: datetime | None = None

        sorted_records = sorted(
            records,
            key=lambda item: item.captured_at,
            reverse=True,
        )

        for record in sorted_records:
            image_files = [
                file_object
                for file_object in record.files
                if file_object.file_kind in {FileKind.ANNOTATED, FileKind.SOURCE, FileKind.THUMBNAIL}
            ]
            total_image_count += len(image_files)

            if image_files:
                record_latest_uploaded_at = max(
                    (
                        file_object.uploaded_at
                        or file_object.storage_last_modified
                        or file_object.created_at
                    )
                    for file_object in image_files
                )
            else:
                record_latest_uploaded_at = record.uploaded_at

            if (
                record_latest_uploaded_at is not None
                and (latest_uploaded_at is None or record_latest_uploaded_at > latest_uploaded_at)
            ):
                latest_uploaded_at = record_latest_uploaded_at

            sample_file = self._select_sample_file(record=record)
            group_state = group_bucket.setdefault(
                record.part_id,
                {
                    "part_id": record.part_id,
                    "part_code": record.part.part_code,
                    "part_name": record.part.name,
                    "part_category": record.part.category,
                    "record_count": 0,
                    "image_count": 0,
                    "latest_uploaded_at": None,
                    "items": [],
                },
            )

            group_state["record_count"] += 1
            group_state["image_count"] += len(image_files)

            if (
                record_latest_uploaded_at is not None
                and (
                    group_state["latest_uploaded_at"] is None
                    or record_latest_uploaded_at > group_state["latest_uploaded_at"]
                )
            ):
                group_state["latest_uploaded_at"] = record_latest_uploaded_at

            group_state["items"].append(
                StatisticsSampleImageItem(
                    record_id=record.id,
                    record_no=record.record_no,
                    part_id=record.part_id,
                    part_code=record.part.part_code,
                    part_name=record.part.name,
                    part_category=record.part.category,
                    device_id=record.device_id,
                    device_code=record.device.device_code,
                    device_name=record.device.name,
                    image_file_id=sample_file.id if sample_file is not None else None,
                    image_file_kind=sample_file.file_kind if sample_file is not None else None,
                    image_count=len(image_files),
                    preview_url=(
                        self._build_file_preview_url(
                            bucket_name=sample_file.bucket_name,
                            region=sample_file.region,
                            object_key=sample_file.object_key,
                        )
                        if sample_file is not None
                        else None
                    ),
                    uploaded_at=record_latest_uploaded_at,
                    captured_at=record.captured_at,
                    effective_result=self._resolve_result(record),
                    review_status=record.review_status,
                    defect_type=record.latest_review.defect_type if record.latest_review and record.latest_review.defect_type else record.defect_type,
                    defect_desc=record.latest_review.comment if record.latest_review and record.latest_review.comment else record.defect_desc,
                )
            )

        groups = [
            StatisticsPartImageGroup(
                part_id=group_state["part_id"],
                part_code=group_state["part_code"],
                part_name=group_state["part_name"],
                part_category=group_state["part_category"],
                record_count=group_state["record_count"],
                image_count=group_state["image_count"],
                latest_uploaded_at=group_state["latest_uploaded_at"],
                items=group_state["items"],
            )
            for group_state in group_bucket.values()
        ]
        groups.sort(
            key=lambda item: (
                -(item.latest_uploaded_at.timestamp() if item.latest_uploaded_at else 0),
                -item.record_count,
                item.part_code,
            ),
        )

        return StatisticsSampleGalleryResponse(
            total_record_count=len(records),
            total_image_count=total_image_count,
            total_part_count=len(groups),
            latest_uploaded_at=latest_uploaded_at,
            groups=groups,
        )

    def get_overview(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        days: int,
        part_id: int | None = None,
        device_id: int | None = None,
    ) -> StatisticsOverviewResponse:
        """返回统计页完整概览数据。"""

        resolved_start_date, resolved_end_date = self._resolve_date_window(
            start_date=start_date,
            end_date=end_date,
            days=days,
        )
        filters = StatisticsFiltersResponse(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            days=days,
            part_id=part_id,
            device_id=device_id,
        )
        records = self._load_records(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            part_id=part_id,
            device_id=device_id,
        )
        summary = self._build_summary_from_records(records=records)
        daily_trend = self._build_daily_trend_from_records(
            records=records,
            start_date=resolved_start_date,
            end_date=resolved_end_date,
        )
        defect_distribution = self._build_defect_distribution_from_records(records=records)
        result_distribution = self._build_result_distribution_from_records(records=records)
        review_status_distribution = self._build_review_status_distribution_from_records(records=records)
        part_quality_ranking = self._build_part_quality_ranking(records=records)
        device_quality_ranking = self._build_device_quality_ranking(records=records)
        key_findings = self._build_key_findings(
            filters=filters,
            summary=summary,
            daily_trend=daily_trend,
            defect_distribution=defect_distribution,
            part_quality_ranking=part_quality_ranking,
            device_quality_ranking=device_quality_ranking,
        )
        sample_gallery = self._build_sample_gallery(records=records)

        return StatisticsOverviewResponse(
            filters=filters,
            summary=summary,
            daily_trend=daily_trend,
            defect_distribution=defect_distribution,
            result_distribution=result_distribution,
            review_status_distribution=review_status_distribution,
            part_quality_ranking=part_quality_ranking,
            device_quality_ranking=device_quality_ranking,
            key_findings=key_findings,
            sample_gallery=sample_gallery,
            generated_at=datetime.now(timezone.utc),
        )

    def get_summary(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> SummaryStatisticsResponse:
        """返回检测记录概览统计。"""

        records = self._load_records(start_date=start_date, end_date=end_date)
        return self._build_summary_from_records(records=records)

    def get_daily_trend(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        days: int,
    ) -> DailyTrendResponse:
        """返回按天聚合的检测趋势统计。"""

        resolved_start_date, resolved_end_date = self._resolve_date_window(
            start_date=start_date,
            end_date=end_date,
            days=days,
        )
        records = self._load_records(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
        )
        return DailyTrendResponse(
            items=self._build_daily_trend_from_records(
                records=records,
                start_date=resolved_start_date,
                end_date=resolved_end_date,
            )
        )

    def get_defect_distribution(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> DefectDistributionResponse:
        """返回缺陷类型分布统计。"""

        records = self._load_records(start_date=start_date, end_date=end_date)
        return DefectDistributionResponse(
            items=self._build_defect_distribution_from_records(records=records)
        )

    def request_ai_analysis(self, payload: StatisticsAIAnalysisRequest) -> StatisticsAIAnalysisResponse:
        """基于当前统计窗口和运行时模型生成批次分析结论。"""

        overview = self.get_overview(
            start_date=payload.start_date,
            end_date=payload.end_date,
            days=payload.days,
            part_id=payload.part_id,
            device_id=payload.device_id,
        )
        model_context = (
            AIGatewayService(self.db).build_runtime_model_context(payload.model_profile_id)
            if payload.model_profile_id is not None
            else None
        )
        provider_hint = payload.provider_hint or (
            f"{model_context['gateway_name']} / {model_context['display_name']}"
            if model_context is not None
            else None
        )

        if model_context is None:
            return StatisticsAIAnalysisResponse(
                status="reserved",
                answer="统计分析 AI 接口已预留，但当前尚未选择可用模型配置。",
                provider_hint=provider_hint,
                generated_at=datetime.now(timezone.utc),
            )

        answer = self.ai_review_client.request_statistics_analysis(
            provider_hint=provider_hint,
            note=payload.note,
            statistics_context=overview.model_dump(mode="json"),
            model_context=model_context,
        )
        return StatisticsAIAnalysisResponse(
            status="completed",
            answer=answer,
            provider_hint=provider_hint,
            generated_at=datetime.now(timezone.utc),
        )

    def stream_ai_analysis(self, payload: StatisticsAIAnalysisRequest) -> Iterator[str]:
        """基于当前统计窗口流式返回批次 AI 分析结论。"""

        overview = self.get_overview(
            start_date=payload.start_date,
            end_date=payload.end_date,
            days=payload.days,
            part_id=payload.part_id,
            device_id=payload.device_id,
        )
        model_context = (
            AIGatewayService(self.db).build_runtime_model_context(payload.model_profile_id)
            if payload.model_profile_id is not None
            else None
        )
        provider_hint = payload.provider_hint or (
            f"{model_context['gateway_name']} / {model_context['display_name']}"
            if model_context is not None
            else None
        )

        def event_stream() -> Iterator[str]:
            """封装统计 AI 分析的 SSE 事件序列。"""

            try:
                started_at = datetime.now(timezone.utc).isoformat()
                initial_status = "streaming" if model_context is not None else "reserved"
                yield format_sse_event(
                    event="meta",
                    payload={
                        "status": initial_status,
                        "answer": "",
                        "provider_hint": provider_hint,
                        "generated_at": started_at,
                    },
                )

                if model_context is None:
                    reserved_answer = "统计分析 AI 接口已预留，但当前尚未选择可用模型配置。"
                    for text_chunk in self.ai_review_client._iter_text_chunks(text=reserved_answer):
                        yield format_sse_event(event="delta", payload={"text": text_chunk})

                    yield format_sse_event(
                        event="done",
                        payload={
                            "status": "reserved",
                            "answer": reserved_answer,
                            "provider_hint": provider_hint,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    return

                answer_chunks: list[str] = []
                for text_chunk in self.ai_review_client.stream_statistics_analysis(
                    provider_hint=provider_hint,
                    note=payload.note,
                    statistics_context=overview.model_dump(mode="json"),
                    model_context=model_context,
                ):
                    answer_chunks.append(text_chunk)
                    yield format_sse_event(event="delta", payload={"text": text_chunk})

                yield format_sse_event(
                    event="done",
                    payload={
                        "status": "completed",
                        "answer": "".join(answer_chunks),
                        "provider_hint": provider_hint,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except AppError as exc:
                yield format_sse_event(
                    event="error",
                    payload=build_sse_error_payload(exc),
                )
            except Exception as exc:  # noqa: BLE001
                yield format_sse_event(
                    event="error",
                    payload={
                        "status_code": 500,
                        "code": "stream_internal_error",
                        "message": "统计 AI 流式输出过程中发生未处理错误。",
                        "details": {"reason": str(exc)},
                    },
                )

        return event_stream()
