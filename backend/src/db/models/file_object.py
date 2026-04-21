"""文件对象 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, CreatedAtMixin, IdMixin
from src.db.models.enums import FileKind, StorageProvider, enum_values

if TYPE_CHECKING:
    from src.db.models.detection_record import DetectionRecord


class FileObject(Base, IdMixin, CreatedAtMixin):
    """文件对象表，保存 COS 中每个图片对象的元数据。"""

    __tablename__ = "file_objects"
    __table_args__ = (
        Index("ix_file_objects_company_id", "company_id"),
        Index("ix_file_objects_detection_record_id", "detection_record_id"),
        Index("ix_file_objects_object_key", "object_key"),
    )

    # 文件冗余保存 company_id，便于后续按公司做空间清理和对象排查。
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    detection_record_id: Mapped[int] = mapped_column(ForeignKey("detection_records.id"), nullable=False)
    file_kind: Mapped[FileKind] = mapped_column(
        SqlEnum(FileKind, name="file_kind_enum", values_callable=enum_values),
        nullable=False,
    )
    storage_provider: Mapped[StorageProvider] = mapped_column(
        SqlEnum(StorageProvider, name="storage_provider_enum", values_callable=enum_values),
        nullable=False,
        default=StorageProvider.COS,
    )
    bucket_name: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    storage_last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 文件对象属于某一条检测记录。
    detection_record: Mapped["DetectionRecord"] = relationship(
        "DetectionRecord",
        back_populates="files",
    )
