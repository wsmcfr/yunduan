"""设备服务实现。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.db.models.device import Device
from src.repositories.device_repository import DeviceRepository
from src.schemas.device import DeviceCreateRequest, DeviceUpdateRequest


class DeviceService:
    """封装设备管理业务流程。"""

    def __init__(self, db: Session) -> None:
        """初始化设备服务依赖。"""

        self.db = db
        self.device_repository = DeviceRepository(db)

    def list_devices(
        self,
        *,
        company_id: int,
        keyword: str | None,
        status: str | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Device]]:
        """分页查询设备列表。"""

        return self.device_repository.list_devices(
            company_id=company_id,
            keyword=keyword,
            status=status,
            skip=skip,
            limit=limit,
        )

    def create_device(self, *, company_id: int, payload: DeviceCreateRequest) -> Device:
        """创建设备档案。"""

        if self.device_repository.get_by_code(payload.device_code, company_id=company_id) is not None:
            raise ConflictError(code="device_code_exists", message="设备编码已存在。")

        device = Device(
            company_id=company_id,
            device_code=payload.device_code,
            name=payload.name,
            device_type=payload.device_type,
            status=payload.status,
            firmware_version=payload.firmware_version,
            ip_address=payload.ip_address,
            last_seen_at=payload.last_seen_at,
        )
        self.device_repository.create(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update_device(self, *, company_id: int, device_id: int, payload: DeviceUpdateRequest) -> Device:
        """更新设备档案。"""

        device = self.device_repository.get_by_id(device_id, company_id=company_id)
        if device is None:
            raise NotFoundError(code="device_not_found", message="设备不存在。")

        if payload.device_code and payload.device_code != device.device_code:
            existed = self.device_repository.get_by_code(payload.device_code, company_id=company_id)
            if existed is not None and existed.id != device_id:
                raise ConflictError(code="device_code_exists", message="设备编码已存在。")
            device.device_code = payload.device_code

        if payload.name is not None:
            device.name = payload.name
        if payload.device_type is not None:
            device.device_type = payload.device_type
        if payload.status is not None:
            device.status = payload.status
        if "firmware_version" in payload.model_fields_set:
            device.firmware_version = payload.firmware_version
        if "ip_address" in payload.model_fields_set:
            device.ip_address = payload.ip_address
        if "last_seen_at" in payload.model_fields_set:
            device.last_seen_at = payload.last_seen_at

        self.device_repository.save(device)
        self.db.commit()
        self.db.refresh(device)
        return device
