"""系统设置路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import (
    get_current_ai_enabled_user,
    get_current_company_admin_user,
    get_current_company_user,
    get_db,
)
from src.db.models.enums import UserRole
from src.db.models.user import User
from src.schemas.ai_gateway import (
    AIDiscoveredModelCandidate,
    AIDiscoveredModelListResponse,
    AIGatewayDiscoveryPreviewRequest,
    AIGatewayCreateRequest,
    AIGatewayDetailResponse,
    AIGatewayListResponse,
    AIGatewayUpdateRequest,
    AIModelProfileCreateRequest,
    AIModelProfileResponse,
    AIModelProfileUpdateRequest,
    AIRuntimeModelOption,
    AIRuntimeModelOptionListResponse,
)
from src.schemas.common import ApiMessageResponse
from src.schemas.system_user import (
    AdminPasswordResetResponse,
    ApprovePasswordChangeRequestResponse,
    SubmitPasswordChangeRequest,
    SystemUserAiPermissionUpdateRequest,
    SystemUserListItem,
    SystemUserListResponse,
    SystemUserStatusUpdateRequest,
    UserPasswordChangeRequestInfo,
)
from src.services.ai_gateway_service import AIGatewayService
from src.services.system_user_service import SystemUserService

router = APIRouter()


@router.get("/ai-models/runtime-options", response_model=AIRuntimeModelOptionListResponse)
def list_runtime_ai_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_ai_enabled_user),
) -> AIRuntimeModelOptionListResponse:
    """返回业务运行时可选的模型列表。"""

    items = AIGatewayService(db).list_runtime_model_options(company_id=current_user.company_id or 0)
    return AIRuntimeModelOptionListResponse(
        items=[
            AIRuntimeModelOption(
                id=item.id,
                display_name=item.display_name,
                upstream_vendor=item.upstream_vendor,
                protocol_type=item.protocol_type,
                user_agent=item.user_agent,
                model_identifier=item.model_identifier,
                supports_vision=item.supports_vision,
                supports_stream=item.supports_stream,
                gateway_id=item.gateway.id,
                gateway_name=item.gateway.name,
                gateway_vendor=item.gateway.vendor,
                base_url=item.base_url_override or item.gateway.base_url,
            )
            for item in items
        ]
    )


@router.get("/users", response_model=SystemUserListResponse)
def list_system_users(
    keyword: str | None = Query(default=None, min_length=1, max_length=128),
    role: UserRole | None = Query(default=None),
    ai_enabled: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> SystemUserListResponse:
    """分页返回管理员系统设置中需要的用户列表。"""

    total, items = SystemUserService(db).list_users(
        company_id=current_user.company_id,
        keyword=keyword,
        role=role,
        can_use_ai_analysis=ai_enabled,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return SystemUserListResponse(
        items=[SystemUserListItem.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch("/users/{user_id}/ai-permission", response_model=SystemUserListItem)
def update_system_user_ai_permission(
    user_id: int,
    payload: SystemUserAiPermissionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> SystemUserListItem:
    """修改指定用户是否允许使用 AI 分析。"""

    user = SystemUserService(db).update_ai_permission(
        company_id=current_user.company_id,
        user_id=user_id,
        can_use_ai_analysis=payload.can_use_ai_analysis,
    )
    return SystemUserListItem.model_validate(user)


@router.patch("/users/{user_id}/status", response_model=SystemUserListItem)
def update_system_user_status(
    user_id: int,
    payload: SystemUserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> SystemUserListItem:
    """修改指定用户的启停状态。"""

    user = SystemUserService(db).update_active_status(
        company_id=current_user.company_id,
        current_user_id=current_user.id,
        user_id=user_id,
        is_active=payload.is_active,
    )
    return SystemUserListItem.model_validate(user)


@router.post("/users/{user_id}/password-reset", response_model=AdminPasswordResetResponse)
def reset_system_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AdminPasswordResetResponse:
    """由公司管理员直接把指定成员密码重置为默认临时密码。"""

    _, applied_password = SystemUserService(db).reset_user_password_to_default(
        company_id=current_user.company_id,
        current_user_id=current_user.id,
        user_id=user_id,
    )
    return AdminPasswordResetResponse(
        message="已将该用户密码重置为默认临时密码。",
        applied_password=applied_password,
    )


@router.get("/users/me/password-request", response_model=UserPasswordChangeRequestInfo)
def get_my_password_change_request(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> UserPasswordChangeRequestInfo:
    """返回当前登录用户的站内改密申请状态。"""

    user = SystemUserService(db).get_password_change_request_info(
        company_id=current_user.company_id,
        user_id=current_user.id,
    )
    return UserPasswordChangeRequestInfo.model_validate(user)


@router.post("/users/me/password-request", response_model=ApiMessageResponse)
def submit_my_password_change_request(
    payload: SubmitPasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> ApiMessageResponse:
    """由当前登录用户提交站内改密申请。"""

    SystemUserService(db).submit_password_change_request(
        company_id=current_user.company_id,
        user_id=current_user.id,
        request_type=payload.request_type,
        new_password=payload.new_password,
    )
    if payload.request_type == "reset_to_default":
        return ApiMessageResponse(
            message="重置为默认密码的申请已提交，待管理员批准后将重置为 Q123456@。",
        )
    return ApiMessageResponse(message="修改为新密码的申请已提交，待管理员批准后生效。")


@router.post(
    "/users/{user_id}/password-request/approve",
    response_model=ApprovePasswordChangeRequestResponse,
)
def approve_system_user_password_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> ApprovePasswordChangeRequestResponse:
    """批准指定用户的站内改密申请。"""

    _, applied_password = SystemUserService(db).approve_password_change_request(
        company_id=current_user.company_id,
        current_user_id=current_user.id,
        user_id=user_id,
    )
    if applied_password is not None:
        return ApprovePasswordChangeRequestResponse(
            message="已批准该用户的默认密码重置申请。",
            applied_password=applied_password,
        )
    return ApprovePasswordChangeRequestResponse(message="已批准该用户的改密申请。")


@router.post("/users/{user_id}/password-request/reject", response_model=ApiMessageResponse)
def reject_system_user_password_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> ApiMessageResponse:
    """拒绝指定用户的站内改密申请。"""

    SystemUserService(db).reject_password_change_request(
        company_id=current_user.company_id,
        current_user_id=current_user.id,
        user_id=user_id,
    )
    return ApiMessageResponse(message="已拒绝该用户的改密申请。")


@router.delete("/users/{user_id}", response_model=ApiMessageResponse)
def delete_system_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> ApiMessageResponse:
    """删除指定用户账号。"""

    SystemUserService(db).delete_user(
        company_id=current_user.company_id,
        current_user_id=current_user.id,
        user_id=user_id,
    )
    return ApiMessageResponse(message="用户账号已删除。")


@router.get("/ai-gateways", response_model=AIGatewayListResponse)
def list_ai_gateways(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AIGatewayListResponse:
    """返回管理员配置中心所需的全部网关与模型配置。"""

    items = AIGatewayService(db).list_gateways(company_id=current_user.company_id or 0)
    return AIGatewayListResponse(
        items=[AIGatewayDetailResponse.model_validate(item) for item in items]
    )


@router.get("/ai-gateways/{gateway_id}/discovered-models", response_model=AIDiscoveredModelListResponse)
def discover_ai_gateway_models(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AIDiscoveredModelListResponse:
    """根据指定网关的 URL 与密钥自动探测可用模型。"""

    items = AIGatewayService(db).discover_gateway_models(
        company_id=current_user.company_id or 0,
        gateway_id=gateway_id,
    )
    return AIDiscoveredModelListResponse(
        items=[AIDiscoveredModelCandidate.model_validate(item) for item in items]
    )


@router.post("/ai-gateways/discovery-preview", response_model=AIDiscoveredModelListResponse)
def preview_ai_gateway_models(
    payload: AIGatewayDiscoveryPreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_company_admin_user),
) -> AIDiscoveredModelListResponse:
    """根据弹窗中临时填写的 URL 与密钥即时探测模型。"""

    items = AIGatewayService(db).preview_gateway_models(payload)
    return AIDiscoveredModelListResponse(
        items=[AIDiscoveredModelCandidate.model_validate(item) for item in items]
    )


@router.post("/ai-gateways", response_model=AIGatewayDetailResponse)
def create_ai_gateway(
    payload: AIGatewayCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AIGatewayDetailResponse:
    """创建新的 AI 网关。"""

    gateway = AIGatewayService(db).create_gateway(
        company_id=current_user.company_id or 0,
        payload=payload,
    )
    return AIGatewayDetailResponse.model_validate(gateway)


@router.put("/ai-gateways/{gateway_id}", response_model=AIGatewayDetailResponse)
def update_ai_gateway(
    gateway_id: int,
    payload: AIGatewayUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AIGatewayDetailResponse:
    """更新指定 AI 网关。"""

    gateway = AIGatewayService(db).update_gateway(
        company_id=current_user.company_id or 0,
        gateway_id=gateway_id,
        payload=payload,
    )
    return AIGatewayDetailResponse.model_validate(gateway)


@router.delete("/ai-gateways/{gateway_id}", response_model=ApiMessageResponse)
def delete_ai_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> ApiMessageResponse:
    """删除指定 AI 网关。"""

    AIGatewayService(db).delete_gateway(
        company_id=current_user.company_id or 0,
        gateway_id=gateway_id,
    )
    return ApiMessageResponse(message="AI 网关已删除。")


@router.post("/ai-gateways/{gateway_id}/models", response_model=AIModelProfileResponse)
def create_ai_model(
    gateway_id: int,
    payload: AIModelProfileCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AIModelProfileResponse:
    """在指定 AI 网关下创建模型配置。"""

    model = AIGatewayService(db).create_model(
        company_id=current_user.company_id or 0,
        gateway_id=gateway_id,
        payload=payload,
    )
    return AIModelProfileResponse.model_validate(model)


@router.put("/ai-models/{model_id}", response_model=AIModelProfileResponse)
def update_ai_model(
    model_id: int,
    payload: AIModelProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> AIModelProfileResponse:
    """更新指定 AI 模型配置。"""

    model = AIGatewayService(db).update_model(
        company_id=current_user.company_id or 0,
        model_id=model_id,
        payload=payload,
    )
    return AIModelProfileResponse.model_validate(model)


@router.delete("/ai-models/{model_id}", response_model=ApiMessageResponse)
def delete_ai_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> ApiMessageResponse:
    """删除指定 AI 模型配置。"""

    AIGatewayService(db).delete_model(
        company_id=current_user.company_id or 0,
        model_id=model_id,
    )
    return ApiMessageResponse(message="AI 模型配置已删除。")
