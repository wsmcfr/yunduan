"""初始数据库结构。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260420_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 MVP 后端所需的基础表结构。"""

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "operator", "reviewer", name="user_role_enum"),
            nullable=False,
            server_default=sa.text("'operator'"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("part_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_parts_part_code", "parts", ["part_code"], unique=True)

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "device_type",
            sa.Enum("mp157", "f4", "gateway", "other", name="device_type_enum"),
            nullable=False,
            server_default=sa.text("'other'"),
        ),
        sa.Column(
            "status",
            sa.Enum("online", "offline", "fault", name="device_status_enum"),
            nullable=False,
            server_default=sa.text("'offline'"),
        ),
        sa.Column("firmware_version", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_devices_device_code", "devices", ["device_code"], unique=True)

    op.create_table(
        "detection_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("record_no", sa.String(length=64), nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column(
            "result",
            sa.Enum("good", "bad", "uncertain", name="detection_result_enum"),
            nullable=False,
        ),
        sa.Column(
            "review_status",
            sa.Enum("pending", "reviewed", "ai_reserved", name="review_status_enum"),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "surface_result",
            sa.Enum("good", "bad", "uncertain", name="surface_detection_result_enum"),
            nullable=True,
        ),
        sa.Column(
            "backlight_result",
            sa.Enum("good", "bad", "uncertain", name="backlight_detection_result_enum"),
            nullable=True,
        ),
        sa.Column(
            "eddy_result",
            sa.Enum("good", "bad", "uncertain", name="eddy_detection_result_enum"),
            nullable=True,
        ),
        sa.Column("defect_type", sa.String(length=128), nullable=True),
        sa.Column("defect_desc", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )
    op.create_index("ix_detection_records_record_no", "detection_records", ["record_no"], unique=True)
    op.create_index("ix_detection_records_part_id", "detection_records", ["part_id"], unique=False)
    op.create_index("ix_detection_records_device_id", "detection_records", ["device_id"], unique=False)
    op.create_index("ix_detection_records_captured_at", "detection_records", ["captured_at"], unique=False)
    op.create_index("ix_detection_records_uploaded_at", "detection_records", ["uploaded_at"], unique=False)

    op.create_table(
        "file_objects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("detection_record_id", sa.Integer(), nullable=False),
        sa.Column(
            "file_kind",
            sa.Enum("source", "annotated", "thumbnail", name="file_kind_enum"),
            nullable=False,
        ),
        sa.Column(
            "storage_provider",
            sa.Enum("cos", name="storage_provider_enum"),
            nullable=False,
            server_default=sa.text("'cos'"),
        ),
        sa.Column("bucket_name", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("etag", sa.String(length=128), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["detection_record_id"], ["detection_records.id"]),
    )
    op.create_index("ix_file_objects_detection_record_id", "file_objects", ["detection_record_id"], unique=False)
    op.create_index("ix_file_objects_object_key", "file_objects", ["object_key"], unique=False)

    op.create_table(
        "review_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("detection_record_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column(
            "review_source",
            sa.Enum("manual", "ai_reserved", name="review_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.Enum("good", "bad", "uncertain", name="review_decision_enum"),
            nullable=False,
        ),
        sa.Column("defect_type", sa.String(length=128), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["detection_record_id"], ["detection_records.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
    )
    op.create_index("ix_review_records_detection_record_id", "review_records", ["detection_record_id"], unique=False)
    op.create_index("ix_review_records_reviewer_id", "review_records", ["reviewer_id"], unique=False)


def downgrade() -> None:
    """回滚 MVP 后端基础表结构。"""

    op.drop_table("review_records")
    op.drop_table("file_objects")
    op.drop_table("detection_records")
    op.drop_table("devices")
    op.drop_table("parts")
    op.drop_table("users")
