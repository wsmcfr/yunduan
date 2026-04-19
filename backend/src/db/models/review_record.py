"""审核记录 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, CreatedAtMixin, IdMixin
from src.db.models.enums import DetectionResult, ReviewSource, enum_values

if TYPE_CHECKING:
    from src.db.models.detection_record import DetectionRecord
    from src.db.models.user import User


class ReviewRecord(Base, IdMixin, CreatedAtMixin):
    """审核记录表，保存人工审核或后续 AI 复核的结果。"""

    __tablename__ = "review_records"
    __table_args__ = (
        Index("ix_review_records_detection_record_id", "detection_record_id"),
        Index("ix_review_records_reviewer_id", "reviewer_id"),
    )

    detection_record_id: Mapped[int] = mapped_column(ForeignKey("detection_records.id"), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_source: Mapped[ReviewSource] = mapped_column(
        SqlEnum(ReviewSource, name="review_source_enum", values_callable=enum_values),
        nullable=False,
    )
    decision: Mapped[DetectionResult] = mapped_column(
        SqlEnum(DetectionResult, name="review_decision_enum", values_callable=enum_values),
        nullable=False,
    )
    defect_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # 审核记录归属检测记录，也可追溯到审核人。
    detection_record: Mapped["DetectionRecord"] = relationship(
        "DetectionRecord",
        back_populates="reviews",
    )
    reviewer: Mapped["User"] = relationship("User", back_populates="reviews")

    @property
    def reviewer_display_name(self) -> str | None:
        """提供给响应层的审核人显示名称。"""

        if self.reviewer is None:
            return None
        return self.reviewer.display_name
