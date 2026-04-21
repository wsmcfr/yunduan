"""引入公司租户模型并迁移历史单租户数据。

该迁移需要兼容两种状态：
1. 全新数据库：尚未执行过任何多租户相关结构变更。
2. 半迁移数据库：`companies` 表和部分 `company_id` 列已经落库，但 Alembic 版本仍停留在 `0005`。

MySQL DDL 默认不走事务，用户如果在第一次执行中途失败，就会留下“部分结构已创建、数据未回填完”的状态。
因此这里不能继续使用“一次性顺序执行”的写法，而要改成：
- 先探测对象是否已存在
- 缺什么补什么
- 数据只回填 `NULL` 或历史默认值
- 最后再收口唯一约束、外键和非空约束
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0006"
down_revision = "20260421_0005"
branch_labels = None
depends_on = None

SYSTEM_COMPANY_NAME = "系统默认公司"
SYSTEM_COMPANY_INVITE_CODE = "SYSDEFAULT01"


def _get_inspector() -> sa.Inspector:
    """返回当前连接的数据库结构检查器。

    迁移内部会多次根据“是否已存在”来决定下一步动作，
    每次都重新拿一次 inspector，避免前一步 DDL 变更后缓存未刷新的问题。
    """

    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    """判断目标表是否已经存在。"""

    return _get_inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    """判断目标表是否已经包含指定列。"""

    if not _has_table(table_name):
        return False

    return any(column["name"] == column_name for column in _get_inspector().get_columns(table_name))


def _get_column(table_name: str, column_name: str) -> dict[str, Any] | None:
    """读取指定列的完整结构定义。

    这里主要用于判断列是否仍然允许 `NULL`，
    从而决定是否需要在迁移末尾把它收口为非空字段。
    """

    if not _has_table(table_name):
        return None

    for column in _get_inspector().get_columns(table_name):
        if column["name"] == column_name:
            return column
    return None


def _find_index(table_name: str, index_name: str) -> dict[str, Any] | None:
    """按名称查找索引定义。"""

    if not _has_table(table_name):
        return None

    for item in _get_inspector().get_indexes(table_name):
        if item.get("name") == index_name:
            return item
    return None


def _has_foreign_key(table_name: str, foreign_key_name: str) -> bool:
    """判断外键是否已经存在。"""

    if not _has_table(table_name):
        return False

    return any(item.get("name") == foreign_key_name for item in _get_inspector().get_foreign_keys(table_name))


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    """判断唯一约束是否已经存在。

    MySQL 下唯一约束通常表现为唯一索引，因此这里同时检查：
    - `get_unique_constraints`
    - `get_indexes(..., unique=True)`
    """

    if not _has_table(table_name):
        return False

    inspector = _get_inspector()
    if any(item.get("name") == constraint_name for item in inspector.get_unique_constraints(table_name)):
        return True

    existing_index = _find_index(table_name, constraint_name)
    return bool(existing_index and existing_index.get("unique"))


def _ensure_table_companies() -> None:
    """确保 `companies` 表和它的基础索引存在。

    这是当前半迁移场景的首个断点：第一次执行时表可能已经创建成功，
    但 Alembic 还没有来得及把版本推进到 `0006`。
    """

    if not _has_table("companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("contact_name", sa.String(length=64), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("invite_code", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("is_system_reserved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    _ensure_index("companies", "ix_companies_name", ["name"], unique=True)
    _ensure_index("companies", "ix_companies_invite_code", ["invite_code"], unique=True)
    _ensure_index("companies", "ix_companies_is_active", ["is_active"], unique=False)


def _ensure_column(table_name: str, column: sa.Column) -> None:
    """确保目标列存在。

    Alembic 在 MySQL 上不会自动忽略“列已存在”的情况，
    所以这里必须先探测再 `add_column`，否则半迁移数据库会再次失败。
    """

    if _has_column(table_name, column.name):
        return

    op.add_column(table_name, column)


def _ensure_index(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool,
) -> None:
    """确保目标索引存在且唯一性符合预期。"""

    existing_index = _find_index(table_name, index_name)
    if existing_index is not None:
        # 历史半迁移数据库里，`ix_parts_part_code / ix_devices_device_code / ix_ai_gateways_name`
        # 可能仍然是旧的全局唯一索引。
        # 如果唯一性与目标结构不一致，这里先删再按目标状态重建。
        if bool(existing_index.get("unique")) == unique:
            return
        op.drop_index(index_name, table_name=table_name)

    op.create_index(index_name, table_name, columns, unique=unique)


def _ensure_foreign_key(
    foreign_key_name: str,
    source_table: str,
    referent_table: str,
    local_columns: list[str],
    remote_columns: list[str],
) -> None:
    """确保目标外键存在。"""

    if _has_foreign_key(source_table, foreign_key_name):
        return

    op.create_foreign_key(
        foreign_key_name,
        source_table,
        referent_table,
        local_columns,
        remote_columns,
    )


def _ensure_unique_constraint(
    table_name: str,
    constraint_name: str,
    columns: list[str],
) -> None:
    """确保目标唯一约束存在。"""

    if _has_unique_constraint(table_name, constraint_name):
        return

    op.create_unique_constraint(constraint_name, table_name, columns)


def _ensure_not_nullable_company_id(table_name: str) -> None:
    """把业务表的 `company_id` 收口为非空字段。

    注意：
    - `users.company_id` 仍需允许为空，因为“申请新公司管理员”在审批前没有归属公司。
    - 其他业务表一旦迁移完成后必须非空，否则租户隔离会失效。
    """

    column = _get_column(table_name, "company_id")
    if column is None or not column.get("nullable", True):
        return

    op.alter_column(
        table_name,
        "company_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def _get_or_create_system_company_id(connection: sa.Connection) -> int:
    """查找或创建承接历史单租户数据的系统保留公司。"""

    companies_table = sa.table(
        "companies",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("contact_name", sa.String()),
        sa.column("note", sa.Text()),
        sa.column("invite_code", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_system_reserved", sa.Boolean()),
    )

    # 优先使用已经标记为系统保留公司的记录，避免误命中用户后来创建的普通公司。
    system_company_id = connection.execute(
        sa.select(companies_table.c.id)
        .where(companies_table.c.is_system_reserved.is_(True))
        .order_by(companies_table.c.id.asc())
        .limit(1)
    ).scalar_one_or_none()

    if system_company_id is None:
        system_company_id = connection.execute(
            sa.select(companies_table.c.id)
            .where(companies_table.c.invite_code == SYSTEM_COMPANY_INVITE_CODE)
            .limit(1)
        ).scalar_one_or_none()

    if system_company_id is None:
        system_company_id = connection.execute(
            sa.select(companies_table.c.id)
            .where(companies_table.c.name == SYSTEM_COMPANY_NAME)
            .limit(1)
        ).scalar_one_or_none()

    if system_company_id is None:
        connection.execute(
            sa.insert(companies_table).values(
                name=SYSTEM_COMPANY_NAME,
                contact_name="平台默认管理员",
                note="由多租户迁移自动创建，用于承接历史单租户存量数据。",
                invite_code=SYSTEM_COMPANY_INVITE_CODE,
                is_active=True,
                is_system_reserved=True,
            )
        )
        system_company_id = connection.execute(
            sa.select(companies_table.c.id)
            .where(companies_table.c.invite_code == SYSTEM_COMPANY_INVITE_CODE)
            .limit(1)
        ).scalar_one()
    else:
        # 如果系统公司是第一次失败时创建出来的半成品记录，这里把关键标记补齐。
        connection.execute(
            companies_table.update()
            .where(companies_table.c.id == system_company_id)
            .values(
                is_active=True,
                is_system_reserved=True,
            )
        )

    return int(system_company_id)


def _backfill_user_company_scope(connection: sa.Connection, system_company_id: int) -> None:
    """回填历史用户的公司归属，同时保留新多租户数据。

    这里只处理“迁移前遗留的老用户”，判断依据是：
    - `company_id IS NULL`
    - `admin_application_status = 'not_applicable'`

    这样可以避开迁移失败后、系统继续运行期间新创建的“待审批公司管理员申请”用户。
    """

    users_table = sa.table(
        "users",
        sa.column("company_id", sa.Integer()),
        sa.column("role", sa.String()),
        sa.column("is_default_admin", sa.Boolean()),
        sa.column("admin_application_status", sa.String()),
    )

    # 历史平台管理员升级为“默认管理员”，并归属到系统保留公司。
    connection.execute(
        users_table.update()
        .where(
            sa.and_(
                users_table.c.company_id.is_(None),
                users_table.c.role == "admin",
                users_table.c.admin_application_status == "not_applicable",
            )
        )
        .values(
            company_id=system_company_id,
            is_default_admin=True,
            admin_application_status="approved",
        )
    )

    # 历史普通用户没有公司归属时，也一并收拢到系统保留公司。
    connection.execute(
        users_table.update()
        .where(
            sa.and_(
                users_table.c.company_id.is_(None),
                users_table.c.admin_application_status == "not_applicable",
            )
        )
        .values(company_id=system_company_id)
    )


def _backfill_business_company_scope(connection: sa.Connection, system_company_id: int) -> None:
    """回填业务表上的 `company_id`。

    回填顺序非常重要：
    1. 先补零件、设备、网关这类“顶层业务对象”
    2. 再让检测记录通过零件/设备推导
    3. 最后让文件和复核记录通过检测记录/复核人推导

    这样可以最大限度保留半迁移期间新增的真实租户归属，而不是一股脑回填到系统公司。
    """

    parts_table = sa.table("parts", sa.column("company_id", sa.Integer()))
    devices_table = sa.table("devices", sa.column("company_id", sa.Integer()))
    ai_gateways_table = sa.table("ai_gateways", sa.column("company_id", sa.Integer()))

    connection.execute(
        parts_table.update()
        .where(parts_table.c.company_id.is_(None))
        .values(company_id=system_company_id)
    )
    connection.execute(
        devices_table.update()
        .where(devices_table.c.company_id.is_(None))
        .values(company_id=system_company_id)
    )
    connection.execute(
        ai_gateways_table.update()
        .where(ai_gateways_table.c.company_id.is_(None))
        .values(company_id=system_company_id)
    )

    # 检测记录优先继承零件或设备的公司归属，只有两者都缺失时才兜底回填系统公司。
    connection.execute(
        sa.text(
            """
            UPDATE detection_records AS dr
            LEFT JOIN parts AS p ON p.id = dr.part_id
            LEFT JOIN devices AS d ON d.id = dr.device_id
            SET dr.company_id = COALESCE(p.company_id, d.company_id, :system_company_id)
            WHERE dr.company_id IS NULL
            """
        ),
        {"system_company_id": system_company_id},
    )

    # 文件对象跟着检测记录走，保证附件和业务主记录位于同一租户。
    connection.execute(
        sa.text(
            """
            UPDATE file_objects AS fo
            LEFT JOIN detection_records AS dr ON dr.id = fo.detection_record_id
            SET fo.company_id = COALESCE(dr.company_id, :system_company_id)
            WHERE fo.company_id IS NULL
            """
        ),
        {"system_company_id": system_company_id},
    )

    # 复核记录优先继承检测记录，其次退化到复核人归属，最后再兜底系统公司。
    connection.execute(
        sa.text(
            """
            UPDATE review_records AS rr
            LEFT JOIN detection_records AS dr ON dr.id = rr.detection_record_id
            LEFT JOIN users AS u ON u.id = rr.reviewer_id
            SET rr.company_id = COALESCE(dr.company_id, u.company_id, :system_company_id)
            WHERE rr.company_id IS NULL
            """
        ),
        {"system_company_id": system_company_id},
    )


def _ensure_schema_columns() -> None:
    """补齐多租户改造需要的全部新列。"""

    _ensure_column("users", sa.Column("company_id", sa.Integer(), nullable=True))
    _ensure_column(
        "users",
        sa.Column("is_default_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    _ensure_column(
        "users",
        sa.Column(
            "admin_application_status",
            sa.Enum(
                "not_applicable",
                "pending",
                "approved",
                "rejected",
                name="admin_application_status_enum",
            ),
            nullable=False,
            server_default=sa.text("'not_applicable'"),
        ),
    )
    _ensure_column("users", sa.Column("requested_company_name", sa.String(length=128), nullable=True))
    _ensure_column(
        "users",
        sa.Column("requested_company_contact_name", sa.String(length=64), nullable=True),
    )
    _ensure_column("users", sa.Column("requested_company_note", sa.Text(), nullable=True))
    _ensure_index("users", "ix_users_company_id", ["company_id"], unique=False)

    _ensure_column("parts", sa.Column("company_id", sa.Integer(), nullable=True))
    _ensure_column("devices", sa.Column("company_id", sa.Integer(), nullable=True))
    _ensure_column("detection_records", sa.Column("company_id", sa.Integer(), nullable=True))
    _ensure_column("ai_gateways", sa.Column("company_id", sa.Integer(), nullable=True))
    _ensure_column("file_objects", sa.Column("company_id", sa.Integer(), nullable=True))
    _ensure_column("review_records", sa.Column("company_id", sa.Integer(), nullable=True))


def _ensure_schema_relationships() -> None:
    """补齐多租户结构依赖的外键、索引和唯一约束。"""

    _ensure_foreign_key("fk_users_company_id_companies", "users", "companies", ["company_id"], ["id"])
    _ensure_foreign_key("fk_parts_company_id_companies", "parts", "companies", ["company_id"], ["id"])
    _ensure_foreign_key("fk_devices_company_id_companies", "devices", "companies", ["company_id"], ["id"])
    _ensure_foreign_key(
        "fk_detection_records_company_id_companies",
        "detection_records",
        "companies",
        ["company_id"],
        ["id"],
    )
    _ensure_foreign_key("fk_ai_gateways_company_id_companies", "ai_gateways", "companies", ["company_id"], ["id"])
    _ensure_foreign_key("fk_file_objects_company_id_companies", "file_objects", "companies", ["company_id"], ["id"])
    _ensure_foreign_key(
        "fk_review_records_company_id_companies",
        "review_records",
        "companies",
        ["company_id"],
        ["id"],
    )

    _ensure_index("parts", "ix_parts_company_id", ["company_id"], unique=False)
    _ensure_index("devices", "ix_devices_company_id", ["company_id"], unique=False)
    _ensure_index("detection_records", "ix_detection_records_company_id", ["company_id"], unique=False)
    _ensure_index("ai_gateways", "ix_ai_gateways_company_id", ["company_id"], unique=False)
    _ensure_index("file_objects", "ix_file_objects_company_id", ["company_id"], unique=False)
    _ensure_index("review_records", "ix_review_records_company_id", ["company_id"], unique=False)

    # 历史单租户模式下这几个字段是“全局唯一”。
    # 多租户改造后它们必须退化为普通索引，再由“公司 + 编码/名称”承担唯一约束。
    _ensure_index("parts", "ix_parts_part_code", ["part_code"], unique=False)
    _ensure_index("devices", "ix_devices_device_code", ["device_code"], unique=False)
    _ensure_index("ai_gateways", "ix_ai_gateways_name", ["name"], unique=False)

    _ensure_unique_constraint("parts", "uq_parts_company_part_code", ["company_id", "part_code"])
    _ensure_unique_constraint("devices", "uq_devices_company_device_code", ["company_id", "device_code"])
    _ensure_unique_constraint("ai_gateways", "uq_ai_gateways_company_name", ["company_id", "name"])


def upgrade() -> None:
    """创建公司表，并把历史单租户数据整体迁移到系统保留公司。"""

    _ensure_table_companies()
    _ensure_schema_columns()

    connection = op.get_bind()
    system_company_id = _get_or_create_system_company_id(connection)

    _backfill_user_company_scope(connection, system_company_id)
    _backfill_business_company_scope(connection, system_company_id)

    _ensure_not_nullable_company_id("parts")
    _ensure_not_nullable_company_id("devices")
    _ensure_not_nullable_company_id("detection_records")
    _ensure_not_nullable_company_id("ai_gateways")
    _ensure_not_nullable_company_id("file_objects")
    _ensure_not_nullable_company_id("review_records")

    _ensure_schema_relationships()


def downgrade() -> None:
    """回滚公司租户改造。

    注意：如果多租户模式下已经产生跨公司重复编码，回滚时恢复全局唯一索引可能失败。
    """

    op.drop_constraint("uq_ai_gateways_company_name", "ai_gateways", type_="unique")
    op.drop_constraint("uq_devices_company_device_code", "devices", type_="unique")
    op.drop_constraint("uq_parts_company_part_code", "parts", type_="unique")

    op.drop_index("ix_ai_gateways_name", table_name="ai_gateways")
    op.drop_index("ix_devices_device_code", table_name="devices")
    op.drop_index("ix_parts_part_code", table_name="parts")

    op.create_index("ix_parts_part_code", "parts", ["part_code"], unique=True)
    op.create_index("ix_devices_device_code", "devices", ["device_code"], unique=True)
    op.create_index("ix_ai_gateways_name", "ai_gateways", ["name"], unique=True)

    op.drop_index("ix_review_records_company_id", table_name="review_records")
    op.drop_index("ix_file_objects_company_id", table_name="file_objects")
    op.drop_index("ix_ai_gateways_company_id", table_name="ai_gateways")
    op.drop_index("ix_detection_records_company_id", table_name="detection_records")
    op.drop_index("ix_devices_company_id", table_name="devices")
    op.drop_index("ix_parts_company_id", table_name="parts")
    op.drop_index("ix_users_company_id", table_name="users")

    op.drop_constraint("fk_review_records_company_id_companies", "review_records", type_="foreignkey")
    op.drop_constraint("fk_file_objects_company_id_companies", "file_objects", type_="foreignkey")
    op.drop_constraint("fk_ai_gateways_company_id_companies", "ai_gateways", type_="foreignkey")
    op.drop_constraint("fk_detection_records_company_id_companies", "detection_records", type_="foreignkey")
    op.drop_constraint("fk_devices_company_id_companies", "devices", type_="foreignkey")
    op.drop_constraint("fk_parts_company_id_companies", "parts", type_="foreignkey")
    op.drop_constraint("fk_users_company_id_companies", "users", type_="foreignkey")

    op.drop_column("review_records", "company_id")
    op.drop_column("file_objects", "company_id")
    op.drop_column("ai_gateways", "company_id")
    op.drop_column("detection_records", "company_id")
    op.drop_column("devices", "company_id")
    op.drop_column("parts", "company_id")

    op.drop_column("users", "requested_company_note")
    op.drop_column("users", "requested_company_contact_name")
    op.drop_column("users", "requested_company_name")
    op.drop_column("users", "admin_application_status")
    op.drop_column("users", "is_default_admin")
    op.drop_column("users", "company_id")

    op.drop_index("ix_companies_is_active", table_name="companies")
    op.drop_index("ix_companies_invite_code", table_name="companies")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
