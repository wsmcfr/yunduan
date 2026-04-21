"""用户 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin
from src.db.models.enums import AdminApplicationStatus, UserRole, enum_values

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.review_record import ReviewRecord


class User(Base, IdMixin, TimestampMixin):
    """系统用户表，负责登录和审核身份归属。"""

    __tablename__ = "users"

    # 用户名是登录主键，必须保持唯一。
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 邮箱用于注册通知和找回密码。
    email: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    # 密码只存哈希值，避免明文泄漏风险。
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 密码最近一次被设置或重置的时间，用于使旧会话失效。
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role_enum", values_callable=enum_values),
        nullable=False,
        default=UserRole.OPERATOR,
        server_default=text("'operator'"),
    )
    # 公司归属是多租户隔离的核心字段。
    # 默认管理员也会挂到“系统保留公司”下，从而承接历史存量数据。
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    # 平台只有一个默认管理员，它拥有审批新公司、停用/删除公司等平台级权限。
    is_default_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    # 该状态只对“申请成为新公司管理员”的注册路径生效。
    admin_application_status: Mapped[AdminApplicationStatus] = mapped_column(
        SqlEnum(
            AdminApplicationStatus,
            name="admin_application_status_enum",
            values_callable=enum_values,
        ),
        nullable=False,
        default=AdminApplicationStatus.NOT_APPLICABLE,
        server_default=text("'not_applicable'"),
    )
    requested_company_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_company_contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_company_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    # AI 分析权限由管理员显式授予，默认关闭，避免新账号自动占用模型能力。
    can_use_ai_analysis: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 重置令牌只保存哈希值，数据库里不落明文 token。
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    password_reset_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 站内审批式改密流程：
    # 用户可以申请“重置为默认密码”或“改成自己提交的新密码”，
    # 待管理员批准后才真正落到正式密码哈希字段中。
    password_change_request_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_change_request_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_change_requested_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_change_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_change_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 用户归属到某个公司；平台默认管理员也会关联到系统保留公司。
    company: Mapped["Company | None"] = relationship("Company", back_populates="users")
    # 一个用户可以拥有多条人工审核记录。
    reviews: Mapped[list["ReviewRecord"]] = relationship("ReviewRecord", back_populates="reviewer")
