"""零件服务实现。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.db.models.part import Part
from src.repositories.part_repository import PartRepository
from src.schemas.part import PartCreateRequest, PartUpdateRequest


class PartService:
    """封装零件管理的业务流程。"""

    def __init__(self, db: Session) -> None:
        """初始化零件服务依赖。"""

        self.db = db
        self.part_repository = PartRepository(db)

    def list_parts(
        self,
        *,
        company_id: int,
        keyword: str | None,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Part]]:
        """分页查询零件列表。

        查询前会清理历史模拟数据留下的无效 `SIM-PART-*` 类型；这些类型通常是
        删除设备及其检测记录后遗留的占位零件，没有任何记录引用时不应继续出现在
        零件管理页。普通手动新增零件不会走这条清理路径。
        """

        self.part_repository.delete_unused_simulated_parts(company_id=company_id)
        self.db.commit()

        total, items = self.part_repository.list_parts(
            company_id=company_id,
            keyword=keyword,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        self._attach_usage_summary(company_id=company_id, items=items)
        return total, items

    def _attach_usage_summary(self, *, company_id: int, items: list[Part]) -> None:
        """为零件类型对象补充检测使用情况，便于前端展示活跃度。"""

        usage_map = self.part_repository.summarize_detection_usage(
            company_id=company_id,
            part_ids=[item.id for item in items],
        )

        for item in items:
            usage_summary = usage_map.get(item.id, {})
            setattr(item, "record_count", int(usage_summary.get("record_count", 0) or 0))
            setattr(item, "image_count", int(usage_summary.get("image_count", 0) or 0))
            setattr(item, "device_count", int(usage_summary.get("device_count", 0) or 0))
            setattr(item, "latest_source_device", usage_summary.get("latest_source_device"))
            setattr(item, "latest_captured_at", usage_summary.get("latest_captured_at"))
            setattr(item, "latest_uploaded_at", usage_summary.get("latest_uploaded_at"))

    def create_part(self, *, company_id: int, payload: PartCreateRequest) -> Part:
        """创建新的零件定义。"""

        if self.part_repository.get_by_code(payload.part_code, company_id=company_id) is not None:
            raise ConflictError(code="part_code_exists", message="零件编码已存在。")

        part = Part(
            company_id=company_id,
            part_code=payload.part_code,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            is_active=payload.is_active,
        )
        self.part_repository.create(part)
        self.db.commit()
        self.db.refresh(part)
        return part

    def update_part(self, *, company_id: int, part_id: int, payload: PartUpdateRequest) -> Part:
        """更新指定零件定义。"""

        part = self.part_repository.get_by_id(part_id, company_id=company_id)
        if part is None:
            raise NotFoundError(code="part_not_found", message="零件不存在。")

        if payload.part_code and payload.part_code != part.part_code:
            existed = self.part_repository.get_by_code(payload.part_code, company_id=company_id)
            if existed is not None and existed.id != part_id:
                raise ConflictError(code="part_code_exists", message="零件编码已存在。")
            part.part_code = payload.part_code

        if payload.name is not None:
            part.name = payload.name
        if "category" in payload.model_fields_set:
            part.category = payload.category
        if "description" in payload.model_fields_set:
            part.description = payload.description
        if payload.is_active is not None:
            part.is_active = payload.is_active

        self.part_repository.save(part)
        self.db.commit()
        self.db.refresh(part)
        return part
