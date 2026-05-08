"""检测记录仓储实现。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, ReviewStatus
from src.db.models.file_object import FileObject
from src.db.models.part import Part
from src.db.models.review_record import ReviewRecord

UNCATEGORIZED_PART_CATEGORY_LABEL = "未分类"


class DetectionRecordRepository:
    """封装检测记录及其文件对象的数据库访问。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求对应的数据库会话。"""

        self.db = db

    def _base_stmt(self) -> Select[tuple[DetectionRecord]]:
        """返回检测记录查询基础语句。"""

        return select(DetectionRecord)

    def _apply_filters(
        self,
        stmt: Select[tuple[DetectionRecord]],
        *,
        part_id: int | None = None,
        part_category: str | None = None,
        device_id: int | None = None,
        result: DetectionResult | None = None,
        review_status: ReviewStatus | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
        uploaded_from: datetime | None = None,
        uploaded_to: datetime | None = None,
    ) -> Select[tuple[DetectionRecord]]:
        """将列表过滤条件统一附加到查询语句上。"""

        if part_id is not None:
            stmt = stmt.where(DetectionRecord.part_id == part_id)
        if part_category:
            if part_category == UNCATEGORIZED_PART_CATEGORY_LABEL:
                stmt = stmt.where(
                    DetectionRecord.part.has(
                        or_(Part.category.is_(None), Part.category == "")
                    )
                )
            else:
                stmt = stmt.where(DetectionRecord.part.has(Part.category == part_category))
        if device_id is not None:
            stmt = stmt.where(DetectionRecord.device_id == device_id)
        if result is not None:
            stmt = stmt.where(DetectionRecord.result == result)
        if review_status is not None:
            stmt = stmt.where(DetectionRecord.review_status == review_status)
        if captured_from is not None:
            stmt = stmt.where(DetectionRecord.captured_at >= captured_from)
        if captured_to is not None:
            stmt = stmt.where(DetectionRecord.captured_at <= captured_to)
        if uploaded_from is not None:
            stmt = stmt.where(DetectionRecord.uploaded_at >= uploaded_from)
        if uploaded_to is not None:
            stmt = stmt.where(DetectionRecord.uploaded_at <= uploaded_to)
        return stmt

    def get_by_id(
        self,
        record_id: int,
        *,
        company_id: int | None = None,
        include_related: bool = False,
    ) -> DetectionRecord | None:
        """按主键查询检测记录，可选附带公司边界。"""

        stmt = self._base_stmt().where(DetectionRecord.id == record_id)
        if company_id is not None:
            stmt = stmt.where(DetectionRecord.company_id == company_id)
        if include_related:
            stmt = stmt.options(
                selectinload(DetectionRecord.part),
                selectinload(DetectionRecord.device),
                selectinload(DetectionRecord.files),
                selectinload(DetectionRecord.reviews).selectinload(ReviewRecord.reviewer),
            )
        else:
            stmt = stmt.options(
                selectinload(DetectionRecord.part),
                selectinload(DetectionRecord.device),
                selectinload(DetectionRecord.reviews),
            )
        return self.db.scalar(stmt)

    def get_by_record_no(self, record_no: str, *, company_id: int | None = None) -> DetectionRecord | None:
        """按业务编号查询检测记录。"""

        stmt = self._base_stmt().where(DetectionRecord.record_no == record_no)
        if company_id is not None:
            stmt = stmt.where(DetectionRecord.company_id == company_id)
        return self.db.scalar(stmt)

    def list_records(
        self,
        *,
        company_id: int,
        part_id: int | None,
        part_category: str | None,
        device_id: int | None,
        result: DetectionResult | None,
        review_status: ReviewStatus | None,
        captured_from: datetime | None,
        captured_to: datetime | None,
        uploaded_from: datetime | None,
        uploaded_to: datetime | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[DetectionRecord]]:
        """查询检测记录分页列表。"""

        stmt = self._apply_filters(
            self._base_stmt().where(DetectionRecord.company_id == company_id),
            part_id=part_id,
            part_category=part_category,
            device_id=device_id,
            result=result,
            review_status=review_status,
            captured_from=captured_from,
            captured_to=captured_to,
            uploaded_from=uploaded_from,
            uploaded_to=uploaded_to,
        )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        data_stmt = (
            stmt.options(
                selectinload(DetectionRecord.part),
                selectinload(DetectionRecord.device),
                selectinload(DetectionRecord.reviews).selectinload(ReviewRecord.reviewer),
            )
            .order_by(DetectionRecord.captured_at.desc(), DetectionRecord.id.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(data_stmt).scalars())
        return total, items

    def list_for_statistics(
        self,
        *,
        company_id: int,
        part_id: int | None = None,
        part_category: str | None = None,
        device_id: int | None = None,
        captured_from: datetime | None,
        captured_to: datetime | None,
    ) -> list[DetectionRecord]:
        """查询统计所需的全量记录集合。"""

        stmt = self._apply_filters(
            self._base_stmt().where(DetectionRecord.company_id == company_id),
            part_id=part_id,
            part_category=part_category,
            device_id=device_id,
            captured_from=captured_from,
            captured_to=captured_to,
        ).options(
            selectinload(DetectionRecord.part),
            selectinload(DetectionRecord.device),
            selectinload(DetectionRecord.files),
            selectinload(DetectionRecord.reviews).selectinload(ReviewRecord.reviewer),
        )
        return list(self.db.execute(stmt).scalars())

    def create(self, record: DetectionRecord) -> DetectionRecord:
        """创建检测主记录。"""

        self.db.add(record)
        self.db.flush()
        return record

    def save(self, record: DetectionRecord) -> DetectionRecord:
        """保存已存在的检测记录。"""

        self.db.add(record)
        self.db.flush()
        return record

    def add_file_object(self, file_object: FileObject) -> FileObject:
        """为检测记录登记新的文件对象。"""

        self.db.add(file_object)
        self.db.flush()
        return file_object

    def delete(self, record: DetectionRecord) -> None:
        """删除指定检测记录聚合并刷新会话状态。

        参数:
            record: 已经按公司边界查出的检测记录对象。

        说明:
            检测记录和文件、审核记录之间配置了 ORM 级联关系；这里仍保持仓储方法，
            让服务层只表达“删除记录聚合”这个业务动作，不直接操作会话细节。
        """

        self.db.delete(record)
        self.db.flush()
