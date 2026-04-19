"""零件仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.part import Part


class PartRepository:
    """封装零件表的查询与持久化逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self) -> Select[tuple[Part]]:
        """返回零件查询基础语句。"""

        return select(Part)

    def get_by_id(self, part_id: int) -> Part | None:
        """按主键查询零件。"""

        return self.db.scalar(self._base_stmt().where(Part.id == part_id))

    def get_by_code(self, part_code: str) -> Part | None:
        """按零件编码查询零件。"""

        return self.db.scalar(self._base_stmt().where(Part.part_code == part_code))

    def list_parts(
        self,
        *,
        keyword: str | None,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Part]]:
        """按过滤条件返回分页后的零件列表。"""

        stmt = self._base_stmt()
        if keyword:
            like_value = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Part.part_code.ilike(like_value),
                    Part.name.ilike(like_value),
                    Part.category.ilike(like_value),
                )
            )
        if is_active is not None:
            stmt = stmt.where(Part.is_active == is_active)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.execute(
                stmt.order_by(Part.created_at.desc(), Part.id.desc()).offset(skip).limit(limit)
            ).scalars()
        )
        return total, items

    def create(self, part: Part) -> Part:
        """创建零件并返回持久化对象。"""

        self.db.add(part)
        self.db.flush()
        return part

    def save(self, part: Part) -> Part:
        """保存已存在的零件对象。"""

        self.db.add(part)
        self.db.flush()
        return part
