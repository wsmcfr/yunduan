"""认证服务实现。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.errors import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError
from src.core.logging import get_logger
from src.core.security import (
    create_access_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password_and_update_hash,
)
from src.db.models.enums import AdminApplicationStatus, UserRole
from src.db.models.user import User
from src.integrations.password_reset_mailer import PasswordResetMailer
from src.repositories.company_repository import CompanyRepository
from src.repositories.user_repository import UserRepository

logger = get_logger(__name__)


class AuthService:
    """封装登录、注册、会话和密码找回逻辑。"""

    def __init__(
        self,
        db: Session,
        password_reset_mailer: PasswordResetMailer | None = None,
    ) -> None:
        """初始化认证服务依赖。"""

        self.db = db
        self.user_repository = UserRepository(db)
        self.company_repository = CompanyRepository(db)
        self.password_reset_mailer = password_reset_mailer or PasswordResetMailer()
        self.settings = get_settings()

    def _normalize_account(self, account: str) -> str:
        """规整登录账号。"""

        return account.strip()

    def _normalize_email(self, email: str) -> str:
        """规整邮箱字段，保证查询和唯一性判断一致。"""

        return email.strip().lower()

    def _normalize_invite_code(self, invite_code: str) -> str:
        """规整公司邀请码。"""

        return invite_code.strip().upper()

    def _resolve_login_user(self, account: str) -> User | None:
        """根据用户名或邮箱查找当前要登录的用户。"""

        normalized_account = self._normalize_account(account)
        if "@" in normalized_account:
            return self.user_repository.get_by_email(self._normalize_email(normalized_account))

        return self.user_repository.get_by_username(normalized_account)

    def _ensure_username_unique(self, username: str) -> None:
        """校验用户名未被占用。"""

        if self.user_repository.get_by_username(username) is not None:
            raise ConflictError(code="username_exists", message="用户名已存在，请更换后再试。")

    def _ensure_email_unique(self, email: str) -> None:
        """校验邮箱未被占用。"""

        if self.user_repository.get_by_email(email) is not None:
            raise ConflictError(code="email_exists", message="邮箱已被注册，请直接登录或找回密码。")

    def _clear_password_reset_state(self, user: User) -> User:
        """清理用户身上的密码重置令牌状态。"""

        user.password_reset_token_hash = None
        user.password_reset_sent_at = None
        user.password_reset_expires_at = None
        return self.user_repository.save(user)

    def login(self, account: str, password: str) -> tuple[str, datetime, User]:
        """校验账号密码并签发访问令牌。"""

        user = self._resolve_login_user(account)
        verified, next_hash = (
            verify_password_and_update_hash(password, user.password_hash)
            if user is not None
            else (False, None)
        )
        if user is None or not verified:
            logger.warning("auth.login_failed account=%s reason=invalid_credentials", account.strip())
            raise UnauthorizedError(code="invalid_credentials", message="账号或密码错误。")
        if user.role == UserRole.ADMIN and not user.is_default_admin:
            if user.admin_application_status == AdminApplicationStatus.PENDING:
                raise ForbiddenError(
                    code="admin_application_pending",
                    message="新公司管理员申请尚未通过平台管理员审批，请稍后再试。",
                )
            if user.admin_application_status == AdminApplicationStatus.REJECTED:
                raise ForbiddenError(
                    code="admin_application_rejected",
                    message="新公司管理员申请已被拒绝，请联系平台管理员。",
                )
            if user.company_id is None:
                raise ForbiddenError(code="company_unavailable", message="当前管理员账号尚未绑定公司。")
        if not user.is_active:
            logger.warning("auth.login_failed account=%s reason=user_disabled", account.strip())
            raise UnauthorizedError(code="user_disabled", message="当前用户已被禁用。")
        if user.company_id is not None:
            company = user.company
            if company is None:
                raise UnauthorizedError(code="company_unavailable", message="当前用户所属公司不存在。")
            if not company.is_active:
                raise ForbiddenError(code="company_inactive", message="当前所属公司已停用，请联系平台管理员。")

        # 老哈希在登录成功时自动升级，避免一次性强制所有账号重置密码。
        if next_hash:
            user.password_hash = next_hash
            if user.password_changed_at is None:
                user.password_changed_at = datetime.now(timezone.utc)
            self.user_repository.save(user)

        self.user_repository.touch_last_login(user)
        self.db.commit()
        self.db.refresh(user)

        token, expires_at = create_access_token(
            subject=str(user.id),
            extra_claims={"username": user.username, "role": user.role.value},
        )
        return token, expires_at, user

    def _build_authenticated_register_result(self, *, user: User) -> dict:
        """为已自动登录的注册结果构造统一返回结构。"""

        token, expires_at = create_access_token(
            subject=str(user.id),
            extra_claims={"username": user.username, "role": user.role.value},
        )
        return {
            "status": "authenticated",
            "message": "注册成功，已自动登录。",
            "token": token,
            "expires_at": expires_at,
            "user": user,
        }

    def _register_invite_join_user(
        self,
        *,
        username: str,
        display_name: str,
        email: str,
        password: str,
        invite_code: str,
    ) -> dict:
        """通过公司邀请码直接注册并加入现有公司。"""

        normalized_invite_code = self._normalize_invite_code(invite_code)
        company = self.company_repository.get_by_invite_code(normalized_invite_code)
        if company is None:
            raise BadRequestError(code="invite_code_invalid", message="邀请码无效，请确认后重试。")
        if not company.is_active:
            raise BadRequestError(code="company_inactive", message="目标公司已停用，当前邀请码不可用。")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            password_changed_at=datetime.now(timezone.utc),
            display_name=display_name,
            role=UserRole.OPERATOR,
            company_id=company.id,
            is_active=True,
            can_use_ai_analysis=False,
        )
        self.user_repository.create(user)
        self.db.commit()
        self.db.refresh(user)
        return self._build_authenticated_register_result(user=user)

    def _register_company_admin_request_user(
        self,
        *,
        username: str,
        display_name: str,
        email: str,
        password: str,
        company_name: str,
        company_contact_name: str,
        company_note: str | None,
    ) -> dict:
        """提交“新公司管理员申请”。"""

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            password_changed_at=datetime.now(timezone.utc),
            display_name=display_name,
            role=UserRole.ADMIN,
            is_active=True,
            can_use_ai_analysis=False,
            admin_application_status=AdminApplicationStatus.PENDING,
            requested_company_name=company_name,
            requested_company_contact_name=company_contact_name,
            requested_company_note=company_note,
        )
        self.user_repository.create(user)
        self.db.commit()
        self.db.refresh(user)
        return {
            "status": "application_submitted",
            "message": "已提交新公司管理员申请，请等待平台默认管理员审批。",
            "token": None,
            "expires_at": None,
            "user": None,
        }

    def register(
        self,
        *,
        register_mode: str,
        username: str,
        display_name: str,
        email: str,
        password: str,
        invite_code: str | None,
        company_name: str | None,
        company_contact_name: str | None,
        company_note: str | None,
    ) -> dict:
        """根据不同注册模式创建账号。"""

        if not self.settings.allow_public_registration:
            raise ForbiddenError(code="public_registration_disabled", message="当前环境未开放自助注册。")

        normalized_username = username.strip()
        normalized_display_name = display_name.strip()
        normalized_email = self._normalize_email(email)
        self._ensure_username_unique(normalized_username)
        self._ensure_email_unique(normalized_email)
        if register_mode == "invite_join":
            return self._register_invite_join_user(
                username=normalized_username,
                display_name=normalized_display_name,
                email=normalized_email,
                password=password,
                invite_code=invite_code or "",
            )

        return self._register_company_admin_request_user(
            username=normalized_username,
            display_name=normalized_display_name,
            email=normalized_email,
            password=password,
            company_name=company_name or "",
            company_contact_name=company_contact_name or "",
            company_note=company_note,
        )

    def request_password_reset(
        self,
        email: str,
        *,
        public_app_url_override: str | None = None,
    ) -> None:
        """生成一次性密码重置令牌，并通过邮件投递。"""

        if not self.password_reset_mailer.is_enabled(public_app_url_override):
            raise BadRequestError(
                code="password_reset_channel_unavailable",
                message="当前环境尚未开启密码找回邮件服务，请联系管理员。",
            )

        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)

        # 为了避免账号枚举，这里对“邮箱不存在 / 账号被停用”统一静默成功。
        if user is None or not user.is_active or not user.email:
            return

        now = datetime.now(timezone.utc)
        previous_sent_at = user.password_reset_sent_at
        if previous_sent_at is not None:
            if previous_sent_at.tzinfo is None:
                previous_sent_at = previous_sent_at.replace(tzinfo=timezone.utc)
            else:
                previous_sent_at = previous_sent_at.astimezone(timezone.utc)

            if now - previous_sent_at < timedelta(seconds=self.settings.password_reset_request_cooldown_seconds):
                return

        raw_token = generate_password_reset_token()
        user.password_reset_token_hash = hash_password_reset_token(raw_token)
        user.password_reset_sent_at = now
        user.password_reset_expires_at = now + timedelta(
            minutes=self.settings.password_reset_token_expire_minutes,
        )
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)

        try:
            self.password_reset_mailer.send_password_reset_mail(
                user=user,
                reset_token=raw_token,
                public_app_url_override=public_app_url_override,
            )
            logger.info(
                "auth.password_reset_requested user_id=%s email=%s",
                user.id,
                user.email,
            )
        except Exception:
            # 邮件没发出去就立即回滚令牌，避免数据库里残留一个无人知晓的有效链接。
            self._clear_password_reset_state(user)
            self.db.commit()
            raise

    def reset_password(self, *, token: str, new_password: str) -> None:
        """校验一次性令牌并更新密码。"""

        token_hash = hash_password_reset_token(token)
        user = self.user_repository.get_by_password_reset_token_hash(token_hash)
        if user is None or not user.is_active:
            raise UnauthorizedError(code="invalid_password_reset_token", message="重置链接无效或已失效。")
        if user.password_reset_expires_at is None:
            raise UnauthorizedError(code="invalid_password_reset_token", message="重置链接无效或已失效。")

        expires_at = user.password_reset_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = expires_at.astimezone(timezone.utc)

        if expires_at < datetime.now(timezone.utc):
            self._clear_password_reset_state(user)
            self.db.commit()
            raise UnauthorizedError(code="password_reset_token_expired", message="重置链接已过期，请重新申请。")

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        self._clear_password_reset_state(user)
        self.db.commit()
        logger.info("auth.password_reset_completed user_id=%s", user.id)
