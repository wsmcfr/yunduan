"""零件仓储实现。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.file_object import FileObject
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

    def summarize_detection_usage(
        self,
        *,
        part_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        """汇总零件类型关联的记录量、图片量、来源设备和最近上传时间。"""

        if not part_ids:
            return {}

        latest_uploaded_expr = func.max(
            func.coalesce(
                FileObject.uploaded_at,
                FileObject.storage_last_modified,
                FileObject.created_at,
                DetectionRecord.uploaded_at,
            )
        )
        stmt = (
            select(
                DetectionRecord.part_id.label("part_id"),
                func.count(func.distinct(DetectionRecord.id)).label("record_count"),
                func.count(FileObject.id).label("image_count"),
                func.count(func.distinct(DetectionRecord.device_id)).label("device_count"),
                func.max(DetectionRecord.captured_at).label("latest_captured_at"),
                latest_uploaded_expr.label("latest_uploaded_at"),
            )
            .select_from(DetectionRecord)
            .outerjoin(FileObject, FileObject.detection_record_id == DetectionRecord.id)
            .where(DetectionRecord.part_id.in_(part_ids))
            .group_by(DetectionRecord.part_id)
        )

        usage_map: dict[int, dict[str, Any]] = {}
        for row in self.db.execute(stmt):
            usage_map[int(row.part_id)] = {
                "record_count": int(row.record_count or 0),
                "image_count": int(row.image_count or 0),
                "device_count": int(row.device_count or 0),
                "latest_captured_at": row.latest_captured_at,
                "latest_uploaded_at": row.latest_uploaded_at,
                "latest_source_device": None,
            }

        latest_source_at_expr = func.coalesce(
            DetectionRecord.uploaded_at,
            DetectionRecord.detected_at,
            DetectionRecord.captured_at,
            DetectionRecord.created_at,
        )
        latest_device_stmt = (
            select(DetectionRecord.part_id, Device)
            .select_from(DetectionRecord)
            .join(Device, Device.id == DetectionRecord.device_id)
            .where(DetectionRecord.part_id.in_(part_ids))
            .order_by(
                DetectionRecord.part_id.asc(),
                latest_source_at_expr.desc(),
                DetectionRecord.id.desc(),
            )
        )

        for row in self.db.execute(latest_device_stmt):
            part_id = int(row.part_id)
            usage_state = usage_map.setdefault(
                part_id,
                {
                    "record_count": 0,
                    "image_count": 0,
                    "device_count": 0,
                    "latest_captured_at": None,
                    "latest_uploaded_at": None,
                    "latest_source_device": None,
                },
            )
            if usage_state["latest_source_device"] is None:
                usage_state["latest_source_device"] = row[1]

        return usage_map

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
