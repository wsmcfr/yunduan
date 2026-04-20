"""AI 模型配置 ORM 模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin
from src.db.models.enums import AIAuthMode, AIModelVendor, AIProtocolType, enum_values


class AIModelProfile(Base, IdMixin, TimestampMixin):
    """AI 模型配置表。

    这一层描述的是“实际运行的模型 + 要走哪种兼容协议”：
    - 同一个网关下可以同时挂 OpenAI-compatible、Claude-compatible、Gemini-compatible 模型
    - 模型切换时，前端只需要提交 `model_profile_id`
    - 后端再根据模型配置和所属网关拼出真实请求
    """

    __tablename__ = "ai_model_profiles"
    __table_args__ = (
        UniqueConstraint("gateway_id", "model_identifier", name="uq_ai_model_profiles_gateway_model"),
        Index("ix_ai_model_profiles_gateway_id", "gateway_id"),
        Index("ix_ai_model_profiles_is_enabled", "is_enabled"),
    )

    gateway_id: Mapped[int] = mapped_column(ForeignKey("ai_gateways.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    upstream_vendor: Mapped[AIModelVendor] = mapped_column(
        SqlEnum(AIModelVendor, name="ai_model_vendor_enum", values_callable=enum_values),
        nullable=False,
    )
    protocol_type: Mapped[AIProtocolType] = mapped_column(
        SqlEnum(AIProtocolType, name="ai_protocol_type_enum", values_callable=enum_values),
        nullable=False,
    )
    auth_mode: Mapped[AIAuthMode] = mapped_column(
        SqlEnum(AIAuthMode, name="ai_auth_mode_enum", values_callable=enum_values),
        nullable=False,
        default=AIAuthMode.AUTHORIZATION_BEARER,
        server_default=text("'authorization_bearer'"),
    )
    base_url_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    supports_vision: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    supports_stream: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 模型配置从属于某个具体网关。
    gateway: Mapped["AIGateway"] = relationship("AIGateway", back_populates="models")
