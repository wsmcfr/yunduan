"""审核记录仓储实现。"""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from src.db.models.review_record import ReviewRecord


class ReviewRepository:
    """封装审核记录的数据库访问逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self) -> Select[tuple[ReviewRecord]]:
        """返回审核记录查询基础语句。"""

        return select(ReviewRecord)

    def list_by_record_id(self, record_id: int) -> list[ReviewRecord]:
        """查询某条检测记录下的全部审核记录。"""

        stmt = (
            self._base_stmt()
            .where(ReviewRecord.detection_record_id == record_id)
            .options(selectinload(ReviewRecord.reviewer))
            .order_by(ReviewRecord.reviewed_at.desc(), ReviewRecord.id.desc())
        )
        return list(self.db.execute(stmt).scalars())

    def create(self, review: ReviewRecord) -> ReviewRecord:
        """创建审核记录。"""

        self.db.add(review)
        self.db.flush()
        return review
