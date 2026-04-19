"""零件 ORM 模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from src.db.models.detection_record import DetectionRecord


class Part(Base, IdMixin, TimestampMixin):
    """零件定义表，维护可检测零件类型与基础说明。"""

    __tablename__ = "parts"

    part_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    # 一个零件类型下会关联多条检测记录。
    detection_records: Mapped[list["DetectionRecord"]] = relationship(
        "DetectionRecord",
        back_populates="part",
    )
