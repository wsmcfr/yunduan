"""add cloud detection context"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260615_0012"
down_revision = "20260519_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为检测记录增加云端模型检测上下文字段。"""

    op.add_column(
        "detection_records",
        sa.Column("cloud_detection_context", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """回滚云端模型检测上下文字段。"""

    op.drop_column("detection_records", "cloud_detection_context")
