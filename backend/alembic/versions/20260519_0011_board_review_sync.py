"""add board review sync fields"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260519_0011"
down_revision = "20260421_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """增加板端复核回写配置和检测记录同步状态字段。"""

    op.add_column("devices", sa.Column("board_review_url", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("board_review_token", sa.String(length=255), nullable=True))
    op.add_column(
        "detection_records",
        sa.Column("board_sync_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "detection_records",
        sa.Column("board_sync_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("detection_records", sa.Column("board_sync_error", sa.Text(), nullable=True))
    op.add_column(
        "detection_records",
        sa.Column("board_last_synced_review_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """回滚板端复核回写配置和同步状态字段。"""

    op.drop_column("detection_records", "board_last_synced_review_id")
    op.drop_column("detection_records", "board_sync_error")
    op.drop_column("detection_records", "board_sync_time")
    op.drop_column("detection_records", "board_sync_status")
    op.drop_column("devices", "board_review_token")
    op.drop_column("devices", "board_review_url")
