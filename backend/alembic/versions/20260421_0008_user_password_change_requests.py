"""为用户表补充站内审批式改密字段。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0008"
down_revision = "20260421_0007"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    """判断指定表上是否已经存在目标列。"""

    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    """在降级时按存在性安全删除列。"""

    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    """为站内审批式重置密码流程补齐所需字段。"""

    if not _has_column("users", "password_change_request_status"):
        op.add_column("users", sa.Column("password_change_request_status", sa.String(length=32), nullable=True))

    if not _has_column("users", "password_change_request_type"):
        op.add_column("users", sa.Column("password_change_request_type", sa.String(length=32), nullable=True))

    if not _has_column("users", "password_change_requested_password_encrypted"):
        op.add_column(
            "users",
            sa.Column("password_change_requested_password_encrypted", sa.Text(), nullable=True),
        )

    if not _has_column("users", "password_change_requested_at"):
        op.add_column(
            "users",
            sa.Column("password_change_requested_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_column("users", "password_change_reviewed_at"):
        op.add_column(
            "users",
            sa.Column("password_change_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    """回滚站内审批式改密字段。"""

    _drop_column_if_exists("users", "password_change_reviewed_at")
    _drop_column_if_exists("users", "password_change_requested_at")
    _drop_column_if_exists("users", "password_change_requested_password_encrypted")
    _drop_column_if_exists("users", "password_change_request_type")
    _drop_column_if_exists("users", "password_change_request_status")
