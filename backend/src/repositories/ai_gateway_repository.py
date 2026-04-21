"""AI 网关配置仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from src.db.models.ai_gateway import AIGateway


class AIGatewayRepository:
    """封装 AI 网关配置表的查询与持久化逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self, *, include_models: bool = False) -> Select[tuple[AIGateway]]:
        """返回 AI 网关查询基础语句。"""

        stmt = select(AIGateway)
        if include_models:
            stmt = stmt.options(selectinload(AIGateway.models))
        return stmt

    def get_by_id(
        self,
        gateway_id: int,
        *,
        company_id: int | None = None,
        include_models: bool = False,
    ) -> AIGateway | None:
        """按主键查询 AI 网关。"""

        stmt = self._base_stmt(include_models=include_models).where(AIGateway.id == gateway_id)
        if company_id is not None:
            stmt = stmt.where(AIGateway.company_id == company_id)
        return self.db.scalar(stmt)

    def get_by_name(self, name: str, *, company_id: int | None = None) -> AIGateway | None:
        """按名称查询 AI 网关。"""

        stmt = self._base_stmt().where(AIGateway.name == name)
        if company_id is not None:
            stmt = stmt.where(AIGateway.company_id == company_id)
        return self.db.scalar(stmt)

    def list_all(self, *, company_id: int) -> list[AIGateway]:
        """按更新时间倒序返回公司内全部 AI 网关，并带出模型配置。"""

        return list(
            self.db.execute(
                self._base_stmt(include_models=True)
                .where(AIGateway.company_id == company_id)
                .order_by(
                    AIGateway.updated_at.desc(),
                    AIGateway.id.desc(),
                )
            ).scalars()
        )

    def create(self, gateway: AIGateway) -> AIGateway:
        """创建 AI 网关并返回持久化对象。"""

        self.db.add(gateway)
        self.db.flush()
        return gateway

    def save(self, gateway: AIGateway) -> AIGateway:
        """保存已存在的 AI 网关对象。"""

        self.db.add(gateway)
        self.db.flush()
        return gateway

    def delete(self, gateway: AIGateway) -> None:
        """删除指定 AI 网关。"""

        self.db.delete(gateway)
