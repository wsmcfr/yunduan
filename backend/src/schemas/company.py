"""公司与管理员申请相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import AdminApplicationStatus
from src.schemas.common import ORMBaseModel


class CompanyBrief(ORMBaseModel):
    """当前用户资料里使用的公司简要信息。"""

    id: int
    name: str
    is_active: bool
    is_system_reserved: bool


class CurrentCompanyResponse(ORMBaseModel):
    """当前公司详情响应体。"""

    id: int
    name: str
    contact_name: str | None
    note: str | None
    invite_code: str
    is_active: bool
    is_system_reserved: bool
    created_at: datetime
    updated_at: datetime


class CompanySummaryResponse(ORMBaseModel):
    """平台管理员查看的公司摘要响应体。"""

    id: int
    name: str
    contact_name: str | None
    note: str | None
    invite_code: str
    is_active: bool
    is_system_reserved: bool
    user_count: int = 0
    part_count: int = 0
    device_count: int = 0
    record_count: int = 0
    gateway_count: int = 0
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    """公司列表分页响应。"""

    items: list[CompanySummaryResponse]
    total: int
    skip: int
    limit: int


class CompanyInviteCodeResetResponse(BaseModel):
    """重置公司邀请码后的响应。"""

    invite_code: str
    message: str


class CompanyAdminApplicationItem(ORMBaseModel):
    """待审批或历史管理员申请摘要。"""

    id: int
    username: str
    email: str | None
    display_name: str
    is_active: bool
    admin_application_status: AdminApplicationStatus
    requested_company_name: str | None
    requested_company_contact_name: str | None
    requested_company_note: str | None
    created_at: datetime
    updated_at: datetime


class CompanyAdminApplicationListResponse(BaseModel):
    """管理员申请列表分页响应。"""

    items: list[CompanyAdminApplicationItem]
    total: int
    skip: int
    limit: int


class PurgeCompanyRequest(BaseModel):
    """彻底删除公司前的二次确认请求体。"""

    confirm_name: str = Field(min_length=1, max_length=128)
