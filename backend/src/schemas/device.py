"""设备相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import DeviceStatus, DeviceType
from src.schemas.common import ORMBaseModel


class DeviceCreateRequest(BaseModel):
    """创建设备请求体。"""

    device_code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    device_type: DeviceType = DeviceType.OTHER
    status: DeviceStatus = DeviceStatus.OFFLINE
    firmware_version: str | None = Field(default=None, max_length=64)
    ip_address: str | None = Field(default=None, max_length=64)
    last_seen_at: datetime | None = None


class DeviceUpdateRequest(BaseModel):
    """更新设备请求体。"""

    device_code: str | None = Field(default=None, min_length=2, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    device_type: DeviceType | None = None
    status: DeviceStatus | None = None
    firmware_version: str | None = Field(default=None, max_length=64)
    ip_address: str | None = Field(default=None, max_length=64)
    last_seen_at: datetime | None = None


class DeviceBrief(ORMBaseModel):
    """检测记录里展示的设备简要信息。"""

    id: int
    device_code: str
    name: str


class DeviceResponse(ORMBaseModel):
    """设备完整响应体。"""

    id: int
    device_code: str
    name: str
    device_type: DeviceType
    status: DeviceStatus
    firmware_version: str | None
    ip_address: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DeviceListResponse(BaseModel):
    """设备列表响应体。"""

    items: list[DeviceResponse]
    total: int
    skip: int
    limit: int
