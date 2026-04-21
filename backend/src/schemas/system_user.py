"""管理员用户管理相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.db.models.enums import UserRole
from src.schemas.common import ORMBaseModel


class SystemUserListItem(ORMBaseModel):
    """管理员在系统设置页看到的用户摘要信息。"""

    id: int
    username: str
    email: str | None
    display_name: str
    role: UserRole
    is_active: bool
    can_use_ai_analysis: bool
    last_login_at: datetime | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SystemUserListResponse(BaseModel):
    """管理员用户列表分页响应。"""

    items: list[SystemUserListItem]
    total: int
    skip: int
    limit: int


class SystemUserAiPermissionUpdateRequest(BaseModel):
    """管理员修改指定用户 AI 使用权限的请求体。"""

    can_use_ai_analysis: bool
