"""为认证体系补充邮箱、会话失效和密码重置字段。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0004"
down_revision = "20260420_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """给用户表增加正式认证所需的安全字段。"""

    op.add_column("users", sa.Column("email", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_reset_token_hash", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("password_reset_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """回滚用户表上的认证安全字段。"""

    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_sent_at")
    op.drop_column("users", "password_reset_token_hash")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email")
