"""检测记录 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, Float, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin
from src.db.models.enums import DetectionResult, ReviewStatus, enum_values

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.device import Device
    from src.db.models.file_object import FileObject
    from src.db.models.part import Part
    from src.db.models.review_record import ReviewRecord


class DetectionRecord(Base, IdMixin, TimestampMixin):
    """检测主记录表，保存一次检测任务的主结果和关键时间字段。"""

    __tablename__ = "detection_records"
    __table_args__ = (
        Index("ix_detection_records_company_id", "company_id"),
        Index("ix_detection_records_part_id", "part_id"),
        Index("ix_detection_records_device_id", "device_id"),
        Index("ix_detection_records_captured_at", "captured_at"),
        Index("ix_detection_records_uploaded_at", "uploaded_at"),
    )

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    record_no: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    result: Mapped[DetectionResult] = mapped_column(
        SqlEnum(DetectionResult, name="detection_result_enum", values_callable=enum_values),
        nullable=False,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        SqlEnum(ReviewStatus, name="review_status_enum", values_callable=enum_values),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default=text("'pending'"),
    )
    surface_result: Mapped[DetectionResult | None] = mapped_column(
        SqlEnum(DetectionResult, name="surface_detection_result_enum", values_callable=enum_values),
        nullable=True,
    )
    backlight_result: Mapped[DetectionResult | None] = mapped_column(
        SqlEnum(DetectionResult, name="backlight_detection_result_enum", values_callable=enum_values),
        nullable=True,
    )
    eddy_result: Mapped[DetectionResult | None] = mapped_column(
        SqlEnum(DetectionResult, name="eddy_detection_result_enum", values_callable=enum_values),
        nullable=True,
    )
    defect_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    defect_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 结构化上下文用于保存设备真实上传的视觉、传感器、判定和设备运行信息。
    # 这里保持 JSON 结构，避免在云端过早把边缘侧数据压扁成少量固定字段。
    vision_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sensor_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    decision_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    device_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 检测记录与零件、设备、文件、审核均形成聚合关系。
    company: Mapped["Company"] = relationship("Company", back_populates="detection_records")
    part: Mapped["Part"] = relationship("Part", back_populates="detection_records")
    device: Mapped["Device"] = relationship("Device", back_populates="detection_records")
    files: Mapped[list["FileObject"]] = relationship(
        "FileObject",
        back_populates="detection_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reviews: Mapped[list["ReviewRecord"]] = relationship(
        "ReviewRecord",
        back_populates="detection_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def latest_review(self) -> "ReviewRecord | None":
        """返回当前检测记录最新的一条审核记录。"""

        if not self.reviews:
            return None

        return max(self.reviews, key=lambda item: (item.reviewed_at, item.id))

    @property
    def effective_result(self) -> DetectionResult:
        """返回前端展示和统计应采用的最终结果。"""

        latest_review = self.latest_review
        if latest_review is not None:
            return latest_review.decision
        return self.result
