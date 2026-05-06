"""设备仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.file_object import FileObject
from src.db.models.review_record import ReviewRecord


class DeviceRepository:
    """封装设备表的查询与持久化逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self) -> Select[tuple[Device]]:
        """返回设备查询基础语句。"""

        return select(Device)

    def get_by_id(self, device_id: int, *, company_id: int | None = None) -> Device | None:
        """按主键查询设备。"""

        stmt = self._base_stmt().where(Device.id == device_id)
        if company_id is not None:
            stmt = stmt.where(Device.company_id == company_id)
        return self.db.scalar(stmt)

    def get_by_code(self, device_code: str, *, company_id: int | None = None) -> Device | None:
        """按设备编码查询设备。"""

        stmt = self._base_stmt().where(Device.device_code == device_code)
        if company_id is not None:
            stmt = stmt.where(Device.company_id == company_id)
        return self.db.scalar(stmt)

    def list_devices(
        self,
        *,
        company_id: int,
        keyword: str | None,
        status: str | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Device]]:
        """按过滤条件返回分页后的设备列表。"""

        stmt = self._base_stmt().where(Device.company_id == company_id)
        if keyword:
            like_value = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Device.device_code.ilike(like_value),
                    Device.name.ilike(like_value),
                    Device.ip_address.ilike(like_value),
                )
            )
        if status is not None:
            stmt = stmt.where(Device.status == status)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.execute(
                stmt.order_by(Device.created_at.desc(), Device.id.desc()).offset(skip).limit(limit)
            ).scalars()
        )
        return total, items

    def summarize_device_usage(self, *, company_id: int, device_ids: list[int]) -> dict[int, dict[str, int]]:
        """汇总设备关联的检测记录数和图片元数据数。"""

        if not device_ids:
            return {}

        usage_map: dict[int, dict[str, int]] = {
            device_id: {"record_count": 0, "image_count": 0}
            for device_id in device_ids
        }
        rows = self.db.execute(
            select(
                DetectionRecord.device_id,
                func.count(func.distinct(DetectionRecord.id)).label("record_count"),
                func.count(func.distinct(FileObject.id)).label("image_count"),
            )
            .select_from(DetectionRecord)
            .outerjoin(FileObject, FileObject.detection_record_id == DetectionRecord.id)
            .where(DetectionRecord.company_id == company_id)
            .where(DetectionRecord.device_id.in_(device_ids))
            .group_by(DetectionRecord.device_id)
        ).all()

        for row in rows:
            usage_map[int(row.device_id)] = {
                "record_count": int(row.record_count or 0),
                "image_count": int(row.image_count or 0),
            }
        return usage_map

    def create(self, device: Device) -> Device:
        """创建设备并返回持久化对象。"""

        self.db.add(device)
        self.db.flush()
        return device

    def save(self, device: Device) -> Device:
        """保存已存在的设备对象。"""

        self.db.add(device)
        self.db.flush()
        return device

    def list_detection_record_ids(self, *, company_id: int, device_id: int) -> list[int]:
        """查询当前公司内引用指定设备的检测记录 ID 列表。"""

        return list(
            self.db.execute(
                select(DetectionRecord.id).where(
                    DetectionRecord.company_id == company_id,
                    DetectionRecord.device_id == device_id,
                )
            ).scalars()
        )

    def list_file_objects_by_record_ids(self, *, company_id: int, record_ids: list[int]) -> list[FileObject]:
        """查询指定检测记录下的文件对象，供彻底删除前清理对象存储。"""

        if not record_ids:
            return []

        return list(
            self.db.execute(
                select(FileObject).where(
                    FileObject.company_id == company_id,
                    FileObject.detection_record_id.in_(record_ids),
                )
            ).scalars()
        )

    def delete_detection_records_by_ids(self, *, company_id: int, record_ids: list[int]) -> None:
        """删除指定检测记录及其审核、文件元数据。

        这里先删除子表，再删除检测主表，避免数据库外键约束阻止删除。
        """

        if not record_ids:
            return

        self.db.execute(
            delete(FileObject).where(
                FileObject.company_id == company_id,
                FileObject.detection_record_id.in_(record_ids),
            )
        )
        self.db.execute(
            delete(ReviewRecord).where(
                ReviewRecord.company_id == company_id,
                ReviewRecord.detection_record_id.in_(record_ids),
            )
        )
        self.db.execute(
            delete(DetectionRecord).where(
                DetectionRecord.company_id == company_id,
                DetectionRecord.id.in_(record_ids),
            )
        )
        self.db.flush()

    def delete(self, device: Device) -> None:
        """删除指定设备对象并刷新会话状态。"""

        self.db.delete(device)
        self.db.flush()
