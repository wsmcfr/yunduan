"""FastAPI 依赖项。"""

from __future__ import annotations

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.errors import ForbiddenError, UnauthorizedError
from src.db.models.enums import UserRole
from src.core.security import decode_access_token
from src.db.models.user import User
from src.repositories.user_repository import UserRepository
from src.db.session import get_db_session

# Bearer 认证依赖负责从请求头中提取 JWT。
bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Session:
    """暴露数据库依赖，供路由直接注入。"""

    yield from get_db_session()


def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """获取当前登录用户的令牌载荷。"""

    if credentials is None:
        raise UnauthorizedError(code="missing_token", message="请求缺少登录凭证。")

    return decode_access_token(credentials.credentials)


def get_current_user(
    token_payload: dict[str, Any] = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> User:
    """根据 JWT 载荷解析当前登录用户。"""

    subject = token_payload.get("sub")
    if subject is None:
        raise UnauthorizedError(code="invalid_token", message="登录凭证缺少用户标识。")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError(code="invalid_token", message="登录凭证中的用户标识非法。") from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError(code="user_unavailable", message="当前登录用户不存在或已被禁用。")

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """要求当前登录用户必须拥有管理员角色。"""

    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError(code="permission_denied", message="只有管理员可以执行当前操作。")

    return current_user
