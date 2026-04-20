"""零件相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.common import ORMBaseModel


class PartCreateRequest(BaseModel):
    """创建零件请求体。"""

    part_code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = None
    is_active: bool = True


class PartUpdateRequest(BaseModel):
    """更新零件请求体。"""

    part_code: str | None = Field(default=None, min_length=2, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    description: str | None = None
    is_active: bool | None = None


class PartBrief(ORMBaseModel):
    """检测记录里展示的零件简要信息。"""

    id: int
    part_code: str
    name: str


class PartResponse(ORMBaseModel):
    """零件完整响应体。"""

    id: int
    part_code: str
    name: str
    category: str | None
    description: str | None
    is_active: bool
    record_count: int = 0
    image_count: int = 0
    latest_captured_at: datetime | None = None
    latest_uploaded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PartListResponse(BaseModel):
    """零件列表响应体。"""

    items: list[PartResponse]
    total: int
    skip: int
    limit: int
