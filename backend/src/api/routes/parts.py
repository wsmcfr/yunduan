"""零件管理路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.schemas.part import PartCreateRequest, PartListResponse, PartResponse, PartUpdateRequest
from src.services.part_service import PartService

router = APIRouter()


@router.get("", response_model=PartListResponse)
def list_parts(
    keyword: str | None = Query(default=None, description="按编码、名称、分类模糊搜索"),
    is_active: bool | None = Query(default=None, description="按启用状态过滤"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PartListResponse:
    """分页获取零件列表。"""

    total, items = PartService(db).list_parts(
        keyword=keyword,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return PartListResponse(
        items=[PartResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PartResponse)
def create_part(
    payload: PartCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PartResponse:
    """创建新的零件定义。"""

    part = PartService(db).create_part(payload)
    return PartResponse.model_validate(part)


@router.put("/{part_id}", response_model=PartResponse)
def update_part(
    part_id: int,
    payload: PartUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PartResponse:
    """更新指定零件定义。"""

    part = PartService(db).update_part(part_id, payload)
    return PartResponse.model_validate(part)
