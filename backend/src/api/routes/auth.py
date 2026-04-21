"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.api.public_app_url import resolve_public_app_url_from_request
from src.api.deps import get_current_user, get_db
from src.core.config import get_settings
from src.core.security import clear_auth_cookie, set_auth_cookie
from src.db.models.user import User
from src.integrations.password_reset_mailer import PasswordResetMailer
from src.schemas.auth import (
    AuthRuntimeOptionsResponse,
    AuthSessionResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserProfile,
)
from src.schemas.common import ApiMessageResponse
from src.services.auth_service import AuthService

router = APIRouter()


@router.get("/runtime-options", response_model=AuthRuntimeOptionsResponse)
def get_runtime_options(request: Request) -> AuthRuntimeOptionsResponse:
    """返回登录注册页所需的运行时认证能力。"""

    settings = get_settings()
    public_app_url_override = resolve_public_app_url_from_request(request)
    return AuthRuntimeOptionsResponse(
        registration_enabled=settings.allow_public_registration,
        password_reset_enabled=PasswordResetMailer(settings).is_enabled(public_app_url_override),
        password_policy_hint="密码需为 8-128 位，并至少包含大写字母、小写字母、数字、符号中的三类。",
    )


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    """处理用户登录并通过 HttpOnly Cookie 建立会话。"""

    token, expires_at, user = AuthService(db).login(payload.account, payload.password)
    set_auth_cookie(response, token=token, expires_at=expires_at)
    return AuthSessionResponse(
        session_expires_at=expires_at,
        user=UserProfile.model_validate(user),
    )


@router.post("/register", response_model=AuthSessionResponse)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    """创建新账号并直接登录。"""

    token, expires_at, user = AuthService(db).register(
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        password=payload.password,
    )
    set_auth_cookie(response, token=token, expires_at=expires_at)
    return AuthSessionResponse(
        session_expires_at=expires_at,
        user=UserProfile.model_validate(user),
    )


@router.post("/logout", response_model=ApiMessageResponse)
def logout(response: Response) -> ApiMessageResponse:
    """清理浏览器中的认证 Cookie。"""

    clear_auth_cookie(response)
    return ApiMessageResponse(message="已退出登录。")


@router.post("/forgot-password", response_model=ApiMessageResponse)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ApiMessageResponse:
    """按邮箱发起密码找回流程。"""

    AuthService(db).request_password_reset(
        payload.email,
        public_app_url_override=resolve_public_app_url_from_request(request),
    )
    return ApiMessageResponse(message="如果该邮箱对应的账号存在，系统已发送密码重置指引。")


@router.post("/reset-password", response_model=ApiMessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiMessageResponse:
    """使用一次性重置令牌设置新密码。"""

    AuthService(db).reset_password(token=payload.token, new_password=payload.new_password)
    clear_auth_cookie(response)
    return ApiMessageResponse(message="密码已重置，请使用新密码重新登录。")


@router.get("/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    """返回当前登录用户信息。"""

    return UserProfile.model_validate(current_user)
