"""新增 AI 网关与模型配置表。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260420_0002"
down_revision = "20260420_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建系统级 AI 网关与模型配置表。"""

    op.create_table(
        "ai_gateways",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "vendor",
            sa.Enum(
                "openai",
                "anthropic",
                "google",
                "zhipu",
                "moonshot",
                "minmax",
                "deepseek",
                "openclaudecode",
                "relay",
                "custom",
                name="ai_gateway_vendor_enum",
            ),
            nullable=False,
        ),
        sa.Column("official_url", sa.String(length=255), nullable=True),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("api_key_last4", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_gateways_name", "ai_gateways", ["name"], unique=True)
    op.create_index(
        "ix_ai_gateways_vendor",
        "ai_gateways",
        ["vendor"],
        unique=False,
    )
    op.create_index(
        "ix_ai_gateways_is_enabled",
        "ai_gateways",
        ["is_enabled"],
        unique=False,
    )

    op.create_table(
        "ai_model_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gateway_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column(
            "upstream_vendor",
            sa.Enum(
                "codex",
                "claude",
                "gemini",
                "deepseek",
                "glm",
                "kimi",
                "minmax",
                "custom",
                name="ai_model_vendor_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "protocol_type",
            sa.Enum(
                "anthropic_messages",
                "openai_compatible",
                "openai_responses",
                "gemini_generate_content",
                name="ai_protocol_type_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "auth_mode",
            sa.Enum(
                "x_api_key",
                "authorization_bearer",
                "both",
                "query_api_key",
                name="ai_auth_mode_enum",
            ),
            nullable=False,
            server_default=sa.text("'authorization_bearer'"),
        ),
        sa.Column("base_url_override", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("model_identifier", sa.String(length=255), nullable=False),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("supports_stream", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["gateway_id"], ["ai_gateways.id"]),
        sa.UniqueConstraint("gateway_id", "model_identifier", name="uq_ai_model_profiles_gateway_model"),
    )
    op.create_index("ix_ai_model_profiles_gateway_id", "ai_model_profiles", ["gateway_id"], unique=False)
    op.create_index("ix_ai_model_profiles_is_enabled", "ai_model_profiles", ["is_enabled"], unique=False)


def downgrade() -> None:
    """回滚 AI 网关与模型配置表。"""

    op.drop_table("ai_model_profiles")
    op.drop_table("ai_gateways")
