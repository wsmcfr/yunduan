"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.api.public_app_url import resolve_public_app_url_from_request
from src.api.deps import get_current_token_payload, get_current_user, get_db
from src.core.config import get_settings
from src.core.errors import UnauthorizedError
from src.core.security import clear_auth_cookie, set_auth_cookie
from src.db.models.user import User
from src.integrations.password_reset_mailer import PasswordResetMailer
from src.schemas.auth import (
    AuthRuntimeOptionsResponse,
    AuthSessionStateResponse,
    RegisterResponse,
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


def _resolve_session_user(request: Request, db: Session) -> User | None:
    """尽量解析当前请求对应的登录用户。

    这里只给公开会话探针使用，因此任何令牌缺失、过期、失效等情况
    都统一回退为“未登录”，避免在登录页产生无意义的 401 控制台噪音。
    """

    try:
        token_payload = get_current_token_payload(request=request, credentials=None)
        return get_current_user(token_payload=token_payload, db=db)
    except UnauthorizedError:
        return None


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


@router.post("/register", response_model=RegisterResponse)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """处理公开注册。

    邀请码注册会直接建立登录态；
    新公司管理员申请只提交审批，不会立刻进入系统。
    """

    result = AuthService(db).register(
        register_mode=payload.register_mode,
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        password=payload.password,
        invite_code=payload.invite_code,
        company_name=payload.company_name,
        company_contact_name=payload.company_contact_name,
        company_note=payload.company_note,
    )
    if result["token"] and result["expires_at"]:
        set_auth_cookie(response, token=result["token"], expires_at=result["expires_at"])
    return RegisterResponse(
        status=result["status"],
        message=result["message"],
        session_expires_at=result["expires_at"],
        user=UserProfile.model_validate(result["user"]) if result["user"] is not None else None,
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


@router.get("/session", response_model=AuthSessionStateResponse)
def get_session_state(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthSessionStateResponse:
    """返回当前浏览器是否仍然持有有效登录会话。"""

    current_user = _resolve_session_user(request=request, db=db)
    if current_user is None:
        return AuthSessionStateResponse(authenticated=False, user=None)

    return AuthSessionStateResponse(
        authenticated=True,
        user=UserProfile.model_validate(current_user),
    )


@router.get("/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    """返回当前登录用户信息。"""

    return UserProfile.model_validate(current_user)
