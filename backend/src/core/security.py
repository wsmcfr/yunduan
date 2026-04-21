"""认证和密码安全工具。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Response
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import get_settings
from src.core.errors import UnauthorizedError

# 这里使用 PBKDF2-SHA256 作为密码 KDF，并显式提高默认轮数。
# 它会为每条密码自动生成随机盐，再叠加服务端 pepper，
# 能显著提高数据库泄露后的离线破解成本。
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=600_000,
)

# 数据库存储精度、ORM 序列化以及 JWT 时间戳精度之间可能存在毫秒级偏差。
# 这里保留极小的容差，避免“刚注册/刚登录就被判定令牌失效”的误伤。
TOKEN_FRESHNESS_SKEW = timedelta(seconds=1)


def _get_password_pepper() -> str:
    """解析当前环境用于口令加固的 pepper。"""

    settings = get_settings()
    return settings.password_pepper or settings.secret_encryption_key or settings.jwt_secret_key


def _apply_password_pepper(password: str) -> str:
    """把明文密码和服务端 pepper 组合成稳定摘要。"""

    normalized_password = password.encode("utf-8")
    pepper = _get_password_pepper().encode("utf-8")
    return hmac.new(pepper, normalized_password, hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    """对明文密码进行正式持久化哈希。"""

    return pwd_context.hash(_apply_password_pepper(password))


def verify_password_and_update_hash(password: str, password_hash: str) -> tuple[bool, str | None]:
    """校验密码，并在需要时返回新的推荐哈希。

    兼容逻辑分两步：
    1. 先按当前“pepper + 慢哈希”正式策略校验。
    2. 如果失败，再兼容旧版未加 pepper 的历史哈希。

    一旦旧版哈希验证成功，就返回新的哈希，调用方可在登录成功时透明升级。
    """

    verified, next_hash = pwd_context.verify_and_update(_apply_password_pepper(password), password_hash)
    if verified:
        return True, next_hash

    legacy_verified, _ = pwd_context.verify_and_update(password, password_hash)
    if legacy_verified:
        return True, hash_password(password)

    return False, None


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """创建 JWT 访问令牌，并返回过期时间。"""

    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expire_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": issued_at,
        "issued_at_ms": int(issued_at.timestamp() * 1000),
        "exp": expire_at,
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expire_at


def decode_access_token(token: str) -> dict[str, Any]:
    """解析 JWT 访问令牌。"""

    settings = get_settings()

    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError(code="invalid_token", message="登录状态无效或已过期。") from exc


def _normalize_datetime(value: datetime) -> datetime:
    """把数据库或 JWT 中的时间统一规整为 UTC 时区。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def validate_token_freshness(
    token_payload: dict[str, Any],
    *,
    password_changed_at: datetime | None,
) -> None:
    """校验令牌签发时间是否仍然晚于最近一次密码修改时间。"""

    if password_changed_at is None:
        return

    raw_issued_at_ms = token_payload.get("issued_at_ms")
    if raw_issued_at_ms is not None:
        try:
            issued_at = datetime.fromtimestamp(int(raw_issued_at_ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError) as exc:
            raise UnauthorizedError(code="invalid_token", message="登录凭证签发时间非法。") from exc
    else:
        raw_issued_at = token_payload.get("iat")
        if raw_issued_at is None:
            raise UnauthorizedError(code="invalid_token", message="登录凭证缺少签发时间。")

        try:
            issued_at = datetime.fromtimestamp(int(raw_issued_at), tz=timezone.utc)
        except (TypeError, ValueError, OSError) as exc:
            raise UnauthorizedError(code="invalid_token", message="登录凭证签发时间非法。") from exc

    normalized_password_changed_at = _normalize_datetime(password_changed_at)

    # 令牌签发时间与密码变更时间在生产环境里可能因为存储精度不同产生极小偏差。
    # 只要差值落在容差窗口内，就认为这是同一次合法会话建立，而不是旧令牌复用。
    if issued_at + TOKEN_FRESHNESS_SKEW < normalized_password_changed_at:
        raise UnauthorizedError(code="token_revoked", message="登录状态已失效，请重新登录。")


def set_auth_cookie(response: Response, *, token: str, expires_at: datetime) -> None:
    """把访问令牌写入服务端 HttpOnly Cookie。"""

    settings = get_settings()
    max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
        domain=settings.auth_cookie_domain_value,
    )


def clear_auth_cookie(response: Response) -> None:
    """清理浏览器中的认证 Cookie。"""

    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        domain=settings.auth_cookie_domain_value,
    )


def generate_password_reset_token() -> str:
    """生成一次性密码重置令牌。"""

    return secrets.token_urlsafe(32)


def hash_password_reset_token(token: str) -> str:
    """把高熵重置令牌转换成只适合服务端比对的摘要值。"""

    normalized_token = token.strip()
    secret = (get_settings().secret_encryption_key or get_settings().jwt_secret_key).encode("utf-8")
    return hmac.new(secret, normalized_token.encode("utf-8"), hashlib.sha256).hexdigest()
