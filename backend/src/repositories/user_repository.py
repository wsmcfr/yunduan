"""用户仓储实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.db.models.user import User


class UserRepository:
    """封装用户表的查询与持久化逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self) -> Select[tuple[User]]:
        """返回用户查询的基础语句，便于后续复用。"""

        return select(User)

    def get_by_id(self, user_id: int) -> User | None:
        """按主键查询用户。"""

        return self.db.scalar(self._base_stmt().where(User.id == user_id))

    def get_by_username(self, username: str) -> User | None:
        """按用户名查询用户。"""

        return self.db.scalar(self._base_stmt().where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        """按邮箱查询用户。"""

        return self.db.scalar(self._base_stmt().where(User.email == email))

    def get_by_password_reset_token_hash(self, token_hash: str) -> User | None:
        """按密码重置令牌哈希查询用户。"""

        return self.db.scalar(self._base_stmt().where(User.password_reset_token_hash == token_hash))

    def create(self, user: User) -> User:
        """创建用户并刷新主键。"""

        self.db.add(user)
        self.db.flush()
        return user

    def save(self, user: User) -> User:
        """保存已存在用户的变更。"""

        self.db.add(user)
        self.db.flush()
        return user

    def touch_last_login(self, user: User) -> User:
        """更新用户最近一次登录时间。"""

        user.last_login_at = datetime.now(timezone.utc)
        return self.save(user)
