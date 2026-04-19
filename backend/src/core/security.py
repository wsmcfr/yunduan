"""认证和密码安全工具。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import get_settings
from src.core.errors import UnauthorizedError

# 这里使用 pbkdf2_sha256 作为默认密码哈希方案。
# 原因是它不依赖额外的 bcrypt 原生模块，Windows 本地开发环境更稳定，
# 对当前 MVP 的账号密码场景也完全够用。
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码进行哈希。"""

    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码是否与哈希值匹配。"""

    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """创建 JWT 访问令牌。"""

    settings = get_settings()
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire_at,
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析 JWT 访问令牌。"""

    settings = get_settings()

    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError(code="invalid_token", message="登录状态无效或已过期。") from exc
