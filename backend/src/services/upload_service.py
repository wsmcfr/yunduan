"""上传服务实现。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.errors import NotFoundError
from src.integrations.cos_client import CosClient
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.schemas.upload import CosUploadPrepareRequest, CosUploadPrepareResponse


class UploadService:
    """封装 COS 上传计划生成逻辑。"""

    def __init__(self, db: Session) -> None:
        """初始化上传服务依赖。"""

        self.db = db
        self.record_repository = DetectionRecordRepository(db)
        self.cos_client = CosClient()

    def prepare_cos_upload(self, payload: CosUploadPrepareRequest) -> CosUploadPrepareResponse:
        """根据记录编号生成上传计划。"""

        record_no = payload.record_no or "unassigned"
        if payload.record_id is not None:
            record = self.record_repository.get_by_id(payload.record_id, include_related=False)
            if record is None:
                raise NotFoundError(code="record_not_found", message="检测记录不存在。")
            record_no = record.record_no

        return CosUploadPrepareResponse.model_validate(
            self.cos_client.prepare_upload(
                record_no=record_no,
                file_kind=payload.file_kind,
                file_name=payload.file_name,
                content_type=payload.content_type,
            )
        )
