"""审核服务实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.core.logging import get_logger
from src.db.models.enums import ReviewSource, ReviewStatus
from src.db.models.review_record import ReviewRecord
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.repositories.review_repository import ReviewRepository
from src.schemas.review import ManualReviewCreateRequest

logger = get_logger(__name__)


class ReviewService:
    """封装人工审核流程。"""

    def __init__(self, db: Session) -> None:
        """初始化审核服务依赖。"""

        self.db = db
        self.record_repository = DetectionRecordRepository(db)
        self.review_repository = ReviewRepository(db)

    def create_manual_review(
        self,
        *,
        company_id: int,
        record_id: int,
        reviewer_id: int,
        payload: ManualReviewCreateRequest,
    ) -> ReviewRecord:
        """为指定检测记录新增一条人工审核记录。"""

        record = self.record_repository.get_by_id(
            record_id,
            company_id=company_id,
            include_related=False,
        )
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        review = ReviewRecord(
            company_id=company_id,
            detection_record_id=record_id,
            reviewer_id=reviewer_id,
            review_source=ReviewSource.MANUAL,
            decision=payload.decision,
            defect_type=payload.defect_type,
            comment=payload.comment,
            reviewed_at=payload.reviewed_at or datetime.now(timezone.utc),
        )
        self.review_repository.create(review)
        record.review_status = ReviewStatus.REVIEWED
        self.record_repository.save(record)
        self.db.commit()
        self.db.refresh(review)
        logger.info(
            "record.review_completed event=record.review_completed record_id=%s reviewer_id=%s decision=%s",
            record_id,
            reviewer_id,
            review.decision.value,
        )
        return review

    def list_reviews(self, *, company_id: int, record_id: int) -> list[ReviewRecord]:
        """返回指定检测记录的全部审核记录。"""

        record = self.record_repository.get_by_id(
            record_id,
            company_id=company_id,
            include_related=False,
        )
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        return self.review_repository.list_by_record_id(record_id)
