"""设备仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.device import Device


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
