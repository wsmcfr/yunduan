"""统计服务实现。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.schemas.statistics import (
    DailyTrendItem,
    DailyTrendResponse,
    DefectDistributionItem,
    DefectDistributionResponse,
    SummaryStatisticsResponse,
)


class StatisticsService:
    """封装概览、趋势和缺陷分布统计逻辑。"""

    def __init__(self, db: Session) -> None:
        """初始化统计服务依赖。"""

        self.db = db
        self.record_repository = DetectionRecordRepository(db)

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

    def _load_records(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> list[DetectionRecord]:
        """按日期范围加载统计需要的检测记录。"""

        captured_from, captured_to = self._to_datetime_range(start_date=start_date, end_date=end_date)
        return self.record_repository.list_for_statistics(
            captured_from=captured_from,
            captured_to=captured_to,
        )

    def _resolve_result(self, record: DetectionRecord) -> DetectionResult:
        """解析一条记录对统计应生效的最终结果。"""

        return record.effective_result

    def get_summary(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> SummaryStatisticsResponse:
        """返回检测记录概览统计。"""

        records = self._load_records(start_date=start_date, end_date=end_date)
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

    def get_daily_trend(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        days: int,
    ) -> DailyTrendResponse:
        """返回按天聚合的检测趋势统计。"""

        if start_date is None and end_date is None:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=max(days - 1, 0))
        elif start_date is None and end_date is not None:
            start_date = end_date - timedelta(days=max(days - 1, 0))
        elif start_date is not None and end_date is None:
            end_date = start_date + timedelta(days=max(days - 1, 0))

        records = self._load_records(start_date=start_date, end_date=end_date)
        bucket: dict[date, Counter] = defaultdict(Counter)

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

        return DailyTrendResponse(items=items)

    def get_defect_distribution(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> DefectDistributionResponse:
        """返回缺陷类型分布统计。"""

        records = self._load_records(start_date=start_date, end_date=end_date)
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

        items = [
            DefectDistributionItem(defect_type=defect_type, count=count)
            for defect_type, count in counter.most_common()
        ]
        return DefectDistributionResponse(items=items)
