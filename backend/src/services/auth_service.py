"""认证服务实现。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.errors import UnauthorizedError
from src.core.security import create_access_token, verify_password
from src.db.models.user import User
from src.repositories.user_repository import UserRepository


class AuthService:
    """封装登录和当前用户读取逻辑。"""

    def __init__(self, db: Session) -> None:
        """初始化认证服务依赖。"""

        self.db = db
        self.user_repository = UserRepository(db)

    def login(self, username: str, password: str) -> tuple[str, User]:
        """校验账号密码并签发访问令牌。"""

        user = self.user_repository.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError(code="invalid_credentials", message="用户名或密码错误。")
        if not user.is_active:
            raise UnauthorizedError(code="user_disabled", message="当前用户已被禁用。")

        self.user_repository.touch_last_login(user)
        self.db.commit()
        self.db.refresh(user)

        token = create_access_token(
            subject=str(user.id),
            extra_claims={"username": user.username, "role": user.role.value},
        )
        return token, user
