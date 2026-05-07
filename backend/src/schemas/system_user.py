"""管理员用户管理相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.db.models.enums import UserRole
from src.schemas.auth import _validate_password_policy
from src.schemas.common import ORMBaseModel
from src.services.system_user_service import DEFAULT_APPROVED_RESET_PASSWORD

PasswordChangeRequestStatus = Literal["pending", "approved", "rejected"] | None
PasswordChangeRequestType = Literal["reset_to_default", "change_to_requested"] | None


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
    password_change_request_status: PasswordChangeRequestStatus
    password_change_request_type: PasswordChangeRequestType
    password_change_requested_at: datetime | None
    password_change_reviewed_at: datetime | None
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


class SystemUserStatusUpdateRequest(BaseModel):
    """管理员修改指定用户启停状态的请求体。"""

    is_active: bool


class UserPasswordChangeRequestInfo(ORMBaseModel):
    """当前用户或管理员查看到的改密申请摘要。"""

    password_change_request_status: PasswordChangeRequestStatus
    password_change_request_type: PasswordChangeRequestType
    password_change_requested_at: datetime | None
    password_change_reviewed_at: datetime | None
    default_reset_password: str = DEFAULT_APPROVED_RESET_PASSWORD


class SubmitPasswordChangeRequest(BaseModel):
    """用户发起站内改密申请的请求体。"""

    request_type: Literal["reset_to_default", "change_to_requested"]
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str | None) -> str | None:
        """当用户申请指定新密码时，沿用统一密码策略。"""

        if value is None:
            return None
        return _validate_password_policy(value)

    @model_validator(mode="after")
    def validate_request_payload(self) -> "SubmitPasswordChangeRequest":
        """根据申请类型校验新密码字段是否齐全。"""

        if self.request_type == "reset_to_default":
            if self.new_password is not None:
                raise ValueError("申请重置为默认密码时，不需要填写新密码。")
        elif self.new_password is None:
            raise ValueError("申请修改为新密码时，必须填写目标密码。")
        return self


class ApprovePasswordChangeRequestResponse(BaseModel):
    """管理员批准改密申请后的响应体。"""

    message: str
    applied_password: str | None = None


class AdminPasswordResetResponse(BaseModel):
    """管理员直接重置成员密码后的响应体。"""

    message: str
    applied_password: str
