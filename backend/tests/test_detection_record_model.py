"""检测记录模型语义测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, ReviewSource, ReviewStatus
from src.db.models.review_record import ReviewRecord
from src.schemas.detection_record import DetectionRecordCreateRequest


class DetectionRecordModelTestCase(unittest.TestCase):
    """验证检测记录最终结果与最新审核记录的边界语义。"""

    def build_record(self, *, result: DetectionResult = DetectionResult.UNCERTAIN) -> DetectionRecord:
        """创建不依赖数据库会话的检测记录对象，供纯模型语义测试使用。"""

        return DetectionRecord(
            id=1,
            record_no="REC-TEST-0001",
            part_id=1,
            device_id=1,
            result=result,
            review_status=ReviewStatus.PENDING,
            surface_result=None,
            backlight_result=None,
            eddy_result=None,
            defect_type=None,
            defect_desc=None,
            confidence_score=None,
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc),
            detected_at=None,
            uploaded_at=None,
            storage_last_modified=None,
        )

    def build_review(
        self,
        *,
        review_id: int,
        decision: DetectionResult,
        reviewed_at: datetime,
    ) -> ReviewRecord:
        """创建审核记录对象，模拟详情页和统计依赖的复核结果。"""

        return ReviewRecord(
            id=review_id,
            detection_record_id=1,
            reviewer_id=1,
            review_source=ReviewSource.MANUAL,
            decision=decision,
            defect_type=None,
            comment=None,
            reviewed_at=reviewed_at,
        )

    def test_effective_result_falls_back_to_initial_result_without_reviews(self) -> None:
        """没有复核记录时，最终结果必须回退到 MP 初检结果。"""

        record = self.build_record(result=DetectionResult.BAD)

        self.assertEqual(record.effective_result, DetectionResult.BAD)
        self.assertIsNone(record.latest_review)

    def test_effective_result_uses_latest_review_decision(self) -> None:
        """存在多条复核记录时，最终结果必须采用最新复核结论。"""

        record = self.build_record(result=DetectionResult.UNCERTAIN)
        base_time = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)
        record.review_status = ReviewStatus.REVIEWED
        record.reviews = [
            self.build_review(
                review_id=1,
                decision=DetectionResult.BAD,
                reviewed_at=base_time,
            ),
            self.build_review(
                review_id=2,
                decision=DetectionResult.GOOD,
                reviewed_at=base_time + timedelta(minutes=5),
            ),
        ]

        self.assertEqual(record.latest_review.id, 2)
        self.assertEqual(record.effective_result, DetectionResult.GOOD)

    def test_latest_review_uses_id_as_tie_breaker_when_time_is_equal(self) -> None:
        """复核时间相同时，需要用更大的记录 ID 作为稳定排序兜底。"""

        record = self.build_record(result=DetectionResult.UNCERTAIN)
        review_time = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)
        record.review_status = ReviewStatus.REVIEWED
        record.reviews = [
            self.build_review(
                review_id=3,
                decision=DetectionResult.BAD,
                reviewed_at=review_time,
            ),
            self.build_review(
                review_id=4,
                decision=DetectionResult.GOOD,
                reviewed_at=review_time,
            ),
        ]

        self.assertEqual(record.latest_review.id, 4)
        self.assertEqual(record.effective_result, DetectionResult.GOOD)

    def test_create_request_accepts_part_code_without_part_id(self) -> None:
        """检测记录创建请求应允许 MP157 只传 part_code 触发服务层自动建零件。"""

        payload = DetectionRecordCreateRequest(
            record_no="REC-AUTO-PART-SCHEMA",
            part_code="wave_washer",
            part_name="波形垫圈",
            part_category="垫圈类",
            auto_create_part=True,
            device_id=1,
            result=DetectionResult.GOOD,
            captured_at=datetime(2026, 5, 20, 3, 39, 59, tzinfo=timezone.utc),
        )

        self.assertIsNone(payload.part_id)
        self.assertEqual(payload.part_code, "wave_washer")
        self.assertEqual(payload.part_name, "波形垫圈")
        self.assertEqual(payload.part_category, "垫圈类")
        self.assertTrue(payload.auto_create_part)

    def test_create_request_normalizes_mp_pending_review_result_aliases(self) -> None:
        """MP157 上传中文待复核结果时，请求 Schema 应统一转成云端稳定枚举。"""

        payload = DetectionRecordCreateRequest(
            record_no="REC-PENDING-REVIEW-SCHEMA",
            part_id=1,
            device_id=1,
            result="待复核",
            surface_result="待确认",
            backlight_result="复核",
            eddy_result="review",
            captured_at=datetime(2026, 5, 20, 3, 39, 59, tzinfo=timezone.utc),
        )

        self.assertEqual(payload.result, DetectionResult.UNCERTAIN)
        self.assertEqual(payload.surface_result, DetectionResult.UNCERTAIN)
        self.assertEqual(payload.backlight_result, DetectionResult.UNCERTAIN)
        self.assertEqual(payload.eddy_result, DetectionResult.UNCERTAIN)
