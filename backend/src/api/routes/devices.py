"""设备管理路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_current_company_admin_user, get_current_company_user, get_db
from src.db.models.enums import DeviceStatus
from src.db.models.user import User
from src.schemas.device import (
    DeviceCreateRequest,
    DeviceDeleteResponse,
    DeviceListResponse,
    DeviceResponse,
    DeviceUpdateRequest,
)
from src.services.device_service import DeviceService

router = APIRouter()


@router.get("", response_model=DeviceListResponse)
def list_devices(
    keyword: str | None = Query(default=None, description="按设备编码、名称、IP 搜索"),
    status: DeviceStatus | None = Query(default=None, description="按设备状态过滤"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> DeviceListResponse:
    """分页获取设备列表。"""

    total, items = DeviceService(db).list_devices(
        company_id=current_user.company_id or 0,
        keyword=keyword,
        status=status,
        skip=skip,
        limit=limit,
    )
    return DeviceListResponse(
        items=[DeviceResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=DeviceResponse)
def create_device(
    payload: DeviceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> DeviceResponse:
    """创建设备档案。"""

    device = DeviceService(db).create_device(company_id=current_user.company_id or 0, payload=payload)
    return DeviceResponse.model_validate(device)


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    payload: DeviceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> DeviceResponse:
    """更新指定设备档案。"""

    device = DeviceService(db).update_device(
        company_id=current_user.company_id or 0,
        device_id=device_id,
        payload=payload,
    )
    return DeviceResponse.model_validate(device)


@router.delete("/{device_id}", response_model=DeviceDeleteResponse)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> DeviceDeleteResponse:
    """彻底删除设备档案及其检测历史。"""

    deleted_record_count = DeviceService(db).delete_device(
        company_id=current_user.company_id or 0,
        device_id=device_id,
    )
    return DeviceDeleteResponse(
        message="设备已彻底删除。",
        deleted_record_count=deleted_record_count,
    )
