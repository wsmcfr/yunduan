"""设备服务实现。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.errors import BadRequestError, ConflictError, NotFoundError
from src.db.models.device import Device
from src.db.models.enums import DeviceType
from src.integrations.cos_client import CosClient
from src.repositories.device_repository import DeviceRepository
from src.schemas.device import DeviceCreateRequest, DeviceUpdateRequest


class DeviceService:
    """封装设备管理业务流程。"""

    def __init__(self, db: Session, cos_client: CosClient | None = None) -> None:
        """初始化设备服务依赖。"""

        self.db = db
        self.device_repository = DeviceRepository(db)
        self.cos_client = cos_client or CosClient()

    def _ensure_mp157_device_type(self, device_type: DeviceType | None) -> None:
        """校验云端设备档案只能登记 STM32MP157 主控。

        F4 通过串口把实时控制和传感器数据上传给 MP157，云端记录这些数据上下文，
        但不把 F4 当成独立在线设备管理。
        """

        if device_type is not None and device_type != DeviceType.MP157:
            raise BadRequestError(
                code="device_type_must_be_mp157",
                message="云端设备管理只登记 STM32MP157 主控设备，F4 数据请通过 MP157 串口上报。",
            )

    def _delete_device_cos_objects(self, *, company_id: int, record_ids: list[int]) -> None:
        """删除设备检测记录关联的 COS 对象。

        对象存储先清理，数据库后清理；如果远端对象删除失败，异常会阻止数据库提交，
        避免数据库元数据没了但 COS 文件仍残留。
        """

        file_objects = self.device_repository.list_file_objects_by_record_ids(
            company_id=company_id,
            record_ids=record_ids,
        )
        unique_files = {
            (item.bucket_name, item.region, item.object_key)
            for item in file_objects
            if item.bucket_name and item.region and item.object_key
        }
        for bucket_name, region, object_key in unique_files:
            self.cos_client.delete_object(
                bucket_name=bucket_name,
                region=region,
                object_key=object_key,
            )

    def list_devices(
        self,
        *,
        company_id: int,
        keyword: str | None,
        status: str | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Device]]:
        """分页查询设备列表，并附加删除确认所需的使用统计。"""

        total, items = self.device_repository.list_devices(
            company_id=company_id,
            keyword=keyword,
            status=status,
            skip=skip,
            limit=limit,
        )
        usage_map = self.device_repository.summarize_device_usage(
            company_id=company_id,
            device_ids=[item.id for item in items],
        )
        for item in items:
            usage = usage_map.get(item.id, {})
            setattr(item, "record_count", int(usage.get("record_count", 0) or 0))
            setattr(item, "image_count", int(usage.get("image_count", 0) or 0))
        return total, items

    def create_device(self, *, company_id: int, payload: DeviceCreateRequest) -> Device:
        """创建设备档案。"""

        self._ensure_mp157_device_type(payload.device_type)

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

        self._ensure_mp157_device_type(payload.device_type)

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

    def delete_device(self, *, company_id: int, device_id: int) -> int:
        """彻底删除设备档案并返回被清理的检测记录数量。

        主要流程：
        1. 先限定公司边界查找设备，避免跨租户误删。
        2. 查出该 MP157 设备关联的检测记录，先清理审核和文件元数据等子记录。
        3. 删除检测主记录和设备档案，并提交同一个事务。
        """

        device = self.device_repository.get_by_id(device_id, company_id=company_id)
        if device is None:
            raise NotFoundError(code="device_not_found", message="设备不存在。")

        record_ids = self.device_repository.list_detection_record_ids(
            company_id=company_id,
            device_id=device_id,
        )
        self._delete_device_cos_objects(company_id=company_id, record_ids=record_ids)
        self.device_repository.delete_detection_records_by_ids(
            company_id=company_id,
            record_ids=record_ids,
        )
        self.device_repository.delete(device)
        self.db.commit()
        return len(record_ids)
