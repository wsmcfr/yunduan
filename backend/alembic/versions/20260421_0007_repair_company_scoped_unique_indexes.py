"""修复多租户改造后残留的旧全局唯一索引。"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260421_0007"
down_revision = "20260421_0006"
branch_labels = None
depends_on = None


def _find_index(inspector: sa.Inspector, table_name: str, index_name: str) -> dict | None:
    """返回指定表上的目标索引定义。"""

    for item in inspector.get_indexes(table_name):
        if item.get("name") == index_name:
            return item
    return None


def _has_unique_constraint(
    inspector: sa.Inspector,
    table_name: str,
    constraint_name: str,
) -> bool:
    """判断目标唯一约束是否已经存在。"""

    for item in inspector.get_unique_constraints(table_name):
        if item.get("name") == constraint_name:
            return True
    return False


def _ensure_non_unique_index(table_name: str, index_name: str, columns: list[str]) -> None:
    """确保旧索引被修复为非唯一索引。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_index = _find_index(inspector, table_name, index_name)

    # 部分数据库实例在多租户迁移前已经存在“全局唯一索引”。
    # 如果该旧索引仍然是 unique，就必须先删掉再按非唯一方式重建，
    # 否则不同公司无法使用相同的网关名、零件编码或设备编码。
    if existing_index is not None and bool(existing_index.get("unique")):
        op.drop_index(index_name, table_name=table_name)
        inspector = sa.inspect(bind)
        existing_index = _find_index(inspector, table_name, index_name)

    if existing_index is None:
        op.create_index(index_name, table_name, columns, unique=False)


def _ensure_unique_constraint(
    table_name: str,
    constraint_name: str,
    columns: list[str],
) -> None:
    """确保公司内唯一约束已经存在。"""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_unique_constraint(inspector, table_name, constraint_name):
        return

    op.create_unique_constraint(constraint_name, table_name, columns)


def upgrade() -> None:
    """修复仍残留旧全局唯一索引的数据库实例。"""

    _ensure_non_unique_index("parts", "ix_parts_part_code", ["part_code"])
    _ensure_non_unique_index("devices", "ix_devices_device_code", ["device_code"])
    _ensure_non_unique_index("ai_gateways", "ix_ai_gateways_name", ["name"])

    _ensure_unique_constraint(
        "parts",
        "uq_parts_company_part_code",
        ["company_id", "part_code"],
    )
    _ensure_unique_constraint(
        "devices",
        "uq_devices_company_device_code",
        ["company_id", "device_code"],
    )
    _ensure_unique_constraint(
        "ai_gateways",
        "uq_ai_gateways_company_name",
        ["company_id", "name"],
    )


def downgrade() -> None:
    """该迁移只做幂等修复，降级时保持 0006 期望的结构不变。"""

