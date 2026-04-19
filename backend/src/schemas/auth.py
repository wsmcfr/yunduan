"""认证相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import UserRole
from src.schemas.common import ORMBaseModel


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class UserProfile(ORMBaseModel):
    """当前登录用户信息。"""

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    """登录成功后的响应体。"""

    access_token: str
    token_type: str = "bearer"
    user: UserProfile
