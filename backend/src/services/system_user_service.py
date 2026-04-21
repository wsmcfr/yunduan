"""管理员用户管理服务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.db.models.enums import UserRole
from src.db.models.user import User
from src.repositories.user_repository import UserRepository


class SystemUserService:
    """封装系统设置页中的用户查询与 AI 权限修改逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求的数据库会话与仓储依赖。"""

        self.db = db
        self.user_repository = UserRepository(db)

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
        """按管理员筛选条件分页返回用户列表。"""

        return self.user_repository.list_users(
            keyword=keyword,
            role=role,
            can_use_ai_analysis=can_use_ai_analysis,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

    def update_ai_permission(self, *, user_id: int, can_use_ai_analysis: bool) -> User:
        """更新指定用户的 AI 分析使用权限。"""

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(code="user_not_found", message="目标用户不存在。")

        user.can_use_ai_analysis = can_use_ai_analysis
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user
