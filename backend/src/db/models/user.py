"""用户 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin
from src.db.models.enums import UserRole, enum_values

if TYPE_CHECKING:
    from src.db.models.review_record import ReviewRecord


class User(Base, IdMixin, TimestampMixin):
    """系统用户表，负责登录和审核身份归属。"""

    __tablename__ = "users"

    # 用户名是登录主键，必须保持唯一。
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 密码只存哈希值，避免明文泄漏风险。
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role_enum", values_callable=enum_values),
        nullable=False,
        default=UserRole.OPERATOR,
        server_default=text("'operator'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 一个用户可以拥有多条人工审核记录。
    reviews: Mapped[list["ReviewRecord"]] = relationship("ReviewRecord", back_populates="reviewer")
