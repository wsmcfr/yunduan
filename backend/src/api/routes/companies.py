"""公司与平台审批路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import (
    get_current_company_admin_user,
    get_current_company_user,
    get_current_platform_admin_user,
    get_db,
)
from src.db.models.enums import AdminApplicationStatus
from src.db.models.user import User
from src.schemas.common import ApiMessageResponse
from src.schemas.company import (
    CompanyAdminApplicationItem,
    CompanyAdminApplicationListResponse,
    CompanyInviteCodeResetResponse,
    CompanyListResponse,
    CompanySummaryResponse,
    CurrentCompanyResponse,
    PurgeCompanyRequest,
)
from src.services.company_service import CompanyService

router = APIRouter()


@router.get("/current", response_model=CurrentCompanyResponse)
def get_current_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> CurrentCompanyResponse:
    """返回当前登录用户所属公司的基础信息。"""

    company = CompanyService(db).get_current_company(company_id=current_user.company_id or 0)
    return CurrentCompanyResponse.model_validate(company)


@router.post("/current/reset-invite-code", response_model=CompanyInviteCodeResetResponse)
def reset_current_company_invite_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> CompanyInviteCodeResetResponse:
    """重置当前公司固定邀请码。"""

    company = CompanyService(db).reset_invite_code(company_id=current_user.company_id or 0)
    return CompanyInviteCodeResetResponse(
        invite_code=company.invite_code,
        message="公司邀请码已重置。",
    )


@router.get("", response_model=CompanyListResponse)
def list_companies(
    keyword: str | None = Query(default=None, min_length=1, max_length=128),
    is_active: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_platform_admin_user),
) -> CompanyListResponse:
    """分页返回平台管理员可见的公司列表。"""

    total, items = CompanyService(db).list_companies(
        keyword=keyword,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return CompanyListResponse(
        items=[CompanySummaryResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/admin-applications", response_model=CompanyAdminApplicationListResponse)
def list_admin_applications(
    keyword: str | None = Query(default=None, min_length=1, max_length=128),
    application_status: AdminApplicationStatus | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_platform_admin_user),
) -> CompanyAdminApplicationListResponse:
    """分页返回新公司管理员申请列表。"""

    total, items = CompanyService(db).list_admin_applications(
        keyword=keyword,
        application_status=application_status,
        skip=skip,
        limit=limit,
    )
    return CompanyAdminApplicationListResponse(
        items=[CompanyAdminApplicationItem.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/admin-applications/{user_id}/approve", response_model=CompanyAdminApplicationItem)
def approve_admin_application(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_platform_admin_user),
) -> CompanyAdminApplicationItem:
    """批准新公司管理员申请并自动创建新公司。"""

    user = CompanyService(db).approve_admin_application(user_id=user_id)
    return CompanyAdminApplicationItem.model_validate(user)


@router.post("/admin-applications/{user_id}/reject", response_model=CompanyAdminApplicationItem)
def reject_admin_application(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_platform_admin_user),
) -> CompanyAdminApplicationItem:
    """拒绝待审批的新公司管理员申请。"""

    user = CompanyService(db).reject_admin_application(user_id=user_id)
    return CompanyAdminApplicationItem.model_validate(user)


@router.post("/{company_id}/deactivate", response_model=CurrentCompanyResponse)
def deactivate_company(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_platform_admin_user),
) -> CurrentCompanyResponse:
    """停用指定公司。"""

    company = CompanyService(db).deactivate_company(company_id=company_id)
    return CurrentCompanyResponse.model_validate(company)


@router.post("/{company_id}/purge", response_model=ApiMessageResponse)
def purge_company(
    company_id: int,
    payload: PurgeCompanyRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_platform_admin_user),
) -> ApiMessageResponse:
    """彻底删除公司以及该公司占用的业务数据和对象存储。"""

    CompanyService(db).purge_company(company_id=company_id, confirm_name=payload.confirm_name)
    return ApiMessageResponse(message="公司已彻底删除。")
