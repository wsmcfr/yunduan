"""为检测记录补充结构化上下文字段。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260420_0003"
down_revision = "20260420_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """给检测记录表新增结构化上下文字段。"""

    op.add_column("detection_records", sa.Column("vision_context", sa.JSON(), nullable=True))
    op.add_column("detection_records", sa.Column("sensor_context", sa.JSON(), nullable=True))
    op.add_column("detection_records", sa.Column("decision_context", sa.JSON(), nullable=True))
    op.add_column("detection_records", sa.Column("device_context", sa.JSON(), nullable=True))


def downgrade() -> None:
    """回滚检测记录结构化上下文字段。"""

    op.drop_column("detection_records", "device_context")
    op.drop_column("detection_records", "decision_context")
    op.drop_column("detection_records", "sensor_context")
    op.drop_column("detection_records", "vision_context")
