"""设备 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin
from src.db.models.enums import DeviceStatus, DeviceType, enum_values

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.detection_record import DetectionRecord


class Device(Base, IdMixin, TimestampMixin):
    """设备档案表，记录云端管理的 MP157 主控设备信息。"""

    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("company_id", "device_code", name="uq_devices_company_device_code"),
        Index("ix_devices_company_id", "company_id"),
    )

    # 同一设备编码只要求在公司内唯一，方便不同公司使用相似命名规则。
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    device_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(
        SqlEnum(DeviceType, name="device_type_enum", values_callable=enum_values),
        nullable=False,
        default=DeviceType.MP157,
        server_default=text("'mp157'"),
    )
    status: Mapped[DeviceStatus] = mapped_column(
        SqlEnum(DeviceStatus, name="device_status_enum", values_callable=enum_values),
        nullable=False,
        default=DeviceStatus.OFFLINE,
        server_default=text("'offline'"),
    )
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 板端复核结果回写接口的完整 URL，由云端后端调用，浏览器端不直接访问开发板。
    board_review_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 板端接口鉴权密钥只允许后端读取和写入，普通响应不得返回明文。
    board_review_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="devices")
    # 一个设备可以产生多条检测记录。
    detection_records: Mapped[list["DetectionRecord"]] = relationship(
        "DetectionRecord",
        back_populates="device",
    )

    @property
    def has_board_review_token(self) -> bool:
        """返回当前设备是否已配置板端回写密钥。"""

        return bool(self.board_review_token)
