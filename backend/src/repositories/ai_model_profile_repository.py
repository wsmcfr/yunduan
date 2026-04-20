"""AI 模型配置仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from src.db.models.ai_model_profile import AIModelProfile


class AIModelProfileRepository:
    """封装 AI 模型配置表的查询与持久化逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self, *, include_gateway: bool = False) -> Select[tuple[AIModelProfile]]:
        """返回 AI 模型配置查询基础语句。"""

        stmt = select(AIModelProfile)
        if include_gateway:
            stmt = stmt.options(selectinload(AIModelProfile.gateway))
        return stmt

    def get_by_id(self, model_id: int, *, include_gateway: bool = False) -> AIModelProfile | None:
        """按主键查询 AI 模型配置。"""

        return self.db.scalar(
            self._base_stmt(include_gateway=include_gateway).where(AIModelProfile.id == model_id)
        )

    def list_runtime_enabled(self) -> list[AIModelProfile]:
        """返回运行时可能被使用的模型配置。"""

        return list(
            self.db.execute(
                self._base_stmt(include_gateway=True).where(AIModelProfile.is_enabled.is_(True))
            ).scalars()
        )

    def create(self, model: AIModelProfile) -> AIModelProfile:
        """创建 AI 模型配置。"""

        self.db.add(model)
        self.db.flush()
        return model

    def save(self, model: AIModelProfile) -> AIModelProfile:
        """保存已存在的 AI 模型配置。"""

        self.db.add(model)
        self.db.flush()
        return model

    def delete(self, model: AIModelProfile) -> None:
        """删除指定 AI 模型配置。"""

        self.db.delete(model)
