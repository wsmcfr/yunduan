"""公司 / 租户 ORM 模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from src.db.models.ai_gateway import AIGateway
    from src.db.models.detection_record import DetectionRecord
    from src.db.models.device import Device
    from src.db.models.part import Part
    from src.db.models.user import User


class Company(Base, IdMixin, TimestampMixin):
    """公司表。

    这里表示真正的业务租户边界：
    - 公司成员通过固定邀请码加入
    - 公司管理员只能管理本公司的网关、设备、零件和检测数据
    - 平台默认管理员可以停用或彻底删除整个公司
    """

    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_invite_code", "invite_code"),
        Index("ix_companies_is_active", "is_active"),
    )

    # 公司名称当前保持全局唯一，避免审批和平台管理列表里出现难以区分的重名租户。
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    # 联系人和备注来自“申请新公司管理员”时提交的资料。
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 每个公司一个固定邀请码，公司管理员可手动重置。
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 停用后的公司不能继续登录和继续使用业务资源。
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    # 系统保留公司用于承接历史单租户存量数据。
    is_system_reserved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    # 以下关系用于公司级级联删除和平台管理概览。
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    parts: Mapped[list["Part"]] = relationship(
        "Part",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    devices: Mapped[list["Device"]] = relationship(
        "Device",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    detection_records: Mapped[list["DetectionRecord"]] = relationship(
        "DetectionRecord",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    ai_gateways: Mapped[list["AIGateway"]] = relationship(
        "AIGateway",
        back_populates="company",
        cascade="all, delete-orphan",
    )
