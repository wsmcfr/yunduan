"""收敛设备类型默认值为 MP157。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0009"
down_revision = "20260421_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """把设备类型默认值从 `other` 调整为 `mp157`。"""

    op.alter_column(
        "devices",
        "device_type",
        existing_type=sa.Enum("mp157", "f4", "gateway", "other", name="device_type_enum"),
        existing_nullable=False,
        server_default=sa.text("'mp157'"),
    )


def downgrade() -> None:
    """回滚设备类型默认值到历史的 `other`。"""

    op.alter_column(
        "devices",
        "device_type",
        existing_type=sa.Enum("mp157", "f4", "gateway", "other", name="device_type_enum"),
        existing_nullable=False,
        server_default=sa.text("'other'"),
    )
