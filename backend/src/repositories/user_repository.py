"""用户仓储实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.db.models.enums import UserRole
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

    def list_users(
        self,
        *,
        keyword: str | None,
        role: UserRole | None,
        can_use_ai_analysis: bool | None,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[User]]:
        """按筛选条件分页返回系统用户列表。"""

        user_stmt = self._base_stmt()
        total_stmt = select(func.count()).select_from(User)

        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            # 用户管理搜索同时覆盖用户名、显示名和邮箱，便于管理员快速定位账号。
            fuzzy_keyword = f"%{normalized_keyword}%"
            keyword_filter = or_(
                User.username.ilike(fuzzy_keyword),
                User.display_name.ilike(fuzzy_keyword),
                User.email.ilike(fuzzy_keyword),
            )
            user_stmt = user_stmt.where(keyword_filter)
            total_stmt = total_stmt.where(keyword_filter)

        if role is not None:
            user_stmt = user_stmt.where(User.role == role)
            total_stmt = total_stmt.where(User.role == role)

        if can_use_ai_analysis is not None:
            user_stmt = user_stmt.where(User.can_use_ai_analysis == can_use_ai_analysis)
            total_stmt = total_stmt.where(User.can_use_ai_analysis == can_use_ai_analysis)

        if is_active is not None:
            user_stmt = user_stmt.where(User.is_active == is_active)
            total_stmt = total_stmt.where(User.is_active == is_active)

        items = list(
            self.db.scalars(
                user_stmt.order_by(User.created_at.desc(), User.id.desc()).offset(skip).limit(limit),
            )
        )
        total = int(self.db.scalar(total_stmt) or 0)
        return total, items

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
