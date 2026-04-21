"""为用户表增加 AI 分析授权字段。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0005"
down_revision = "20260421_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """给用户表增加 AI 使用权限，并为现有管理员补默认授权。"""

    op.add_column(
        "users",
        sa.Column(
            "can_use_ai_analysis",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # 已存在的管理员账号需要继续具备系统运维能力，因此迁移时为管理员补上默认授权。
    op.execute("UPDATE users SET can_use_ai_analysis = 1 WHERE role = 'admin'")


def downgrade() -> None:
    """回滚用户表上的 AI 使用权限字段。"""

    op.drop_column("users", "can_use_ai_analysis")
