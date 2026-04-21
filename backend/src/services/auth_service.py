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
from src.db.models.enums import UserRole
from src.db.models.user import User
from src.integrations.password_reset_mailer import PasswordResetMailer
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
        self.password_reset_mailer = password_reset_mailer or PasswordResetMailer()
        self.settings = get_settings()

    def _normalize_account(self, account: str) -> str:
        """规整登录账号。"""

        return account.strip()

    def _normalize_email(self, email: str) -> str:
        """规整邮箱字段，保证查询和唯一性判断一致。"""

        return email.strip().lower()

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
        if not user.is_active:
            logger.warning("auth.login_failed account=%s reason=user_disabled", account.strip())
            raise UnauthorizedError(code="user_disabled", message="当前用户已被禁用。")

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

    def register(
        self,
        *,
        username: str,
        display_name: str,
        email: str,
        password: str,
    ) -> tuple[str, datetime, User]:
        """创建新账号并直接签发登录会话。"""

        if not self.settings.allow_public_registration:
            raise ForbiddenError(code="public_registration_disabled", message="当前环境未开放自助注册。")

        normalized_username = username.strip()
        normalized_display_name = display_name.strip()
        normalized_email = self._normalize_email(email)
        self._ensure_username_unique(normalized_username)
        self._ensure_email_unique(normalized_email)

        user = User(
            username=normalized_username,
            email=normalized_email,
            password_hash=hash_password(password),
            password_changed_at=datetime.now(timezone.utc),
            display_name=normalized_display_name,
            role=UserRole.OPERATOR,
            is_active=True,
        )
        self.user_repository.create(user)
        self.db.commit()
        self.db.refresh(user)

        token, expires_at = create_access_token(
            subject=str(user.id),
            extra_claims={"username": user.username, "role": user.role.value},
        )
        return token, expires_at, user

    def request_password_reset(self, email: str) -> None:
        """生成一次性密码重置令牌，并通过邮件投递。"""

        if not self.password_reset_mailer.is_enabled():
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
            self.password_reset_mailer.send_password_reset_mail(user=user, reset_token=raw_token)
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
