"""AI 网关配置 ORM 模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, IdMixin, TimestampMixin
from src.db.models.enums import AIGatewayVendor, enum_values

if TYPE_CHECKING:
    from src.db.models.company import Company
    from src.db.models.ai_model_profile import AIModelProfile


class AIGateway(Base, IdMixin, TimestampMixin):
    """系统级 AI 网关配置表。

    这里保存的是“账号 / 中转站 / 网关”层面的公共配置：
    - 品牌名称
    - 基础 URL
    - 密钥

    一个网关下可以挂多条模型配置，从而覆盖“一个中转站代理多个模型”的场景。
    """

    __tablename__ = "ai_gateways"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_ai_gateways_company_name"),
        Index("ix_ai_gateways_company_id", "company_id"),
        Index("ix_ai_gateways_vendor", "vendor"),
        Index("ix_ai_gateways_is_enabled", "is_enabled"),
    )

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    vendor: Mapped[AIGatewayVendor] = mapped_column(
        SqlEnum(AIGatewayVendor, name="ai_gateway_vendor_enum", values_callable=enum_values),
        nullable=False,
    )
    official_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    is_custom: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_last4: Mapped[str] = mapped_column(String(4), nullable=False)

    company: Mapped["Company"] = relationship("Company", back_populates="ai_gateways")
    # 一个网关可以配置多个模型条目，例如同一个中转站下的 Claude / Gemini / Codex。
    models: Mapped[list["AIModelProfile"]] = relationship(
        "AIModelProfile",
        back_populates="gateway",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def has_api_key(self) -> bool:
        """返回当前网关是否已经保存了密钥。"""

        return bool(self.api_key_encrypted)

    @property
    def api_key_mask(self) -> str | None:
        """返回给前端展示的掩码密钥。"""

        if not self.api_key_last4:
            return None

        return f"••••••••{self.api_key_last4}"
