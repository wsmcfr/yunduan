"""认证相关 Schema。"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator

from src.db.models.enums import UserRole
from src.schemas.common import ORMBaseModel

# 用户名、邮箱、密码强度都在入口层做一次明确校验，避免脏数据扩散到服务层。
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _normalize_login_account(value: str) -> str:
    """规整登录时提交的账号标识。"""

    normalized_value = value.strip()
    if len(normalized_value) < 3:
        raise ValueError("请输入有效的用户名或邮箱。")

    return normalized_value


def _normalize_username(value: str) -> str:
    """规整注册用户名并执行格式校验。"""

    normalized_value = value.strip()
    if not USERNAME_PATTERN.fullmatch(normalized_value):
        raise ValueError("用户名需为 3-64 位，只能包含字母、数字、点、下划线或中横线。")

    return normalized_value


def _normalize_email(value: str) -> str:
    """规整邮箱并执行基础格式校验。"""

    normalized_value = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_value):
        raise ValueError("请输入有效的邮箱地址。")

    return normalized_value


def _validate_password_policy(value: str) -> str:
    """校验密码复杂度，避免过于脆弱的口令直接入库。"""

    normalized_value = value.strip()
    if len(normalized_value) < 8 or len(normalized_value) > 128:
        raise ValueError("密码长度需为 8-128 位。")

    categories = 0
    if any(char.islower() for char in normalized_value):
        categories += 1
    if any(char.isupper() for char in normalized_value):
        categories += 1
    if any(char.isdigit() for char in normalized_value):
        categories += 1
    if any(not char.isalnum() for char in normalized_value):
        categories += 1

    if categories < 3:
        raise ValueError("密码需至少包含大写字母、小写字母、数字、符号中的三类。")

    return normalized_value


class AuthRuntimeOptionsResponse(BaseModel):
    """认证页运行时能力描述。"""

    registration_enabled: bool
    password_reset_enabled: bool
    password_policy_hint: str


class LoginRequest(BaseModel):
    """登录请求体。"""

    account: str = Field(
        min_length=3,
        max_length=128,
        validation_alias=AliasChoices("account", "username"),
    )
    password: str = Field(min_length=1, max_length=128)

    @field_validator("account")
    @classmethod
    def validate_account(cls, value: str) -> str:
        """规整登录账号字段。"""

        return _normalize_login_account(value)


class RegisterRequest(BaseModel):
    """注册请求体。"""

    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=2, max_length=64)
    email: str = Field(min_length=5, max_length=128)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """规整用户名。"""

        return _normalize_username(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        """规整展示名称，避免前后空格进入数据库。"""

        normalized_value = value.strip()
        if len(normalized_value) < 2:
            raise ValueError("显示名称至少需要 2 个字符。")

        return normalized_value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """规整邮箱。"""

        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """校验密码复杂度。"""

        return _validate_password_policy(value)


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求体。"""

    email: str = Field(min_length=5, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """规整邮箱。"""

        return _normalize_email(value)


class ResetPasswordRequest(BaseModel):
    """重置密码请求体。"""

    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        """规整重置令牌。"""

        normalized_value = value.strip()
        if len(normalized_value) < 16:
            raise ValueError("重置令牌无效。")

        return normalized_value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        """校验新密码复杂度。"""

        return _validate_password_policy(value)


class UserProfile(ORMBaseModel):
    """当前登录用户信息。"""

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


class AuthSessionResponse(BaseModel):
    """登录或注册成功后的会话响应体。"""

    session_expires_at: datetime
    user: UserProfile
