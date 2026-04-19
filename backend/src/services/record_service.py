"""检测记录服务实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.errors import ConflictError, NotFoundError
from src.core.logging import get_logger
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, FileKind, ReviewStatus
from src.db.models.file_object import FileObject
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.repositories.device_repository import DeviceRepository
from src.repositories.part_repository import PartRepository
from src.schemas.detection_record import DetectionRecordCreateRequest
from src.schemas.review import AIReviewRequest
from src.schemas.upload import FileObjectCreateRequest
from src.integrations.ai_review_client import AIReviewClient

logger = get_logger(__name__)


class RecordService:
    """封装检测记录创建、查询、文件登记和 AI 预留流程。"""

    def __init__(self, db: Session) -> None:
        """初始化检测记录服务依赖。"""

        self.db = db
        self.record_repository = DetectionRecordRepository(db)
        self.part_repository = PartRepository(db)
        self.device_repository = DeviceRepository(db)
        self.ai_review_client = AIReviewClient()

    def _generate_record_no(self) -> str:
        """生成默认检测记录编号。"""

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return f"REC{timestamp}"

    def list_records(
        self,
        *,
        part_id: int | None,
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
        """分页查询检测记录。"""

        return self.record_repository.list_records(
            part_id=part_id,
            device_id=device_id,
            result=result,
            review_status=review_status,
            captured_from=captured_from,
            captured_to=captured_to,
            uploaded_from=uploaded_from,
            uploaded_to=uploaded_to,
            skip=skip,
            limit=limit,
        )

    def create_record(self, payload: DetectionRecordCreateRequest) -> DetectionRecord:
        """创建新的检测主记录。"""

        if self.part_repository.get_by_id(payload.part_id) is None:
            raise NotFoundError(code="part_not_found", message="零件不存在。")
        if self.device_repository.get_by_id(payload.device_id) is None:
            raise NotFoundError(code="device_not_found", message="设备不存在。")

        record_no = payload.record_no or self._generate_record_no()
        if self.record_repository.get_by_record_no(record_no) is not None:
            raise ConflictError(code="record_no_exists", message="检测记录编号已存在。")

        record = DetectionRecord(
            record_no=record_no,
            part_id=payload.part_id,
            device_id=payload.device_id,
            result=payload.result,
            review_status=payload.review_status,
            surface_result=payload.surface_result,
            backlight_result=payload.backlight_result,
            eddy_result=payload.eddy_result,
            defect_type=payload.defect_type,
            defect_desc=payload.defect_desc,
            confidence_score=payload.confidence_score,
            captured_at=payload.captured_at,
            detected_at=payload.detected_at,
            uploaded_at=payload.uploaded_at,
            storage_last_modified=payload.storage_last_modified,
        )
        self.record_repository.create(record)
        self.db.commit()
        record = self.record_repository.get_by_id(record.id, include_related=True)
        logger.info(
            "record.created event=record.created record_id=%s record_no=%s part_id=%s device_id=%s",
            record.id,
            record.record_no,
            record.part_id,
            record.device_id,
        )
        return record

    def get_record_detail(self, record_id: int) -> DetectionRecord:
        """读取检测记录详情。"""

        record = self.record_repository.get_by_id(record_id, include_related=True)
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        # 这里按时间倒序整理详情页展示的文件和审核记录，避免前端重复排序。
        record.files = sorted(
            record.files,
            key=lambda item: (item.uploaded_at or item.created_at, item.id),
            reverse=True,
        )
        record.reviews = sorted(
            record.reviews,
            key=lambda item: (item.reviewed_at, item.id),
            reverse=True,
        )
        return record

    def create_file_object(self, record_id: int, payload: FileObjectCreateRequest) -> FileObject:
        """为指定检测记录登记文件对象元数据。"""

        record = self.record_repository.get_by_id(record_id, include_related=False)
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        uploaded_at = payload.uploaded_at or datetime.now(timezone.utc)
        file_object = FileObject(
            detection_record_id=record_id,
            file_kind=payload.file_kind,
            storage_provider=payload.storage_provider,
            bucket_name=payload.bucket_name,
            region=payload.region,
            object_key=payload.object_key,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            etag=payload.etag,
            uploaded_at=uploaded_at,
            storage_last_modified=payload.storage_last_modified,
        )
        self.record_repository.add_file_object(file_object)

        # 主记录上只保留结果图的主上传时间；没有结果图时退回到原图时间。
        if payload.file_kind in {FileKind.ANNOTATED, FileKind.SOURCE}:
            if record.uploaded_at is None or payload.file_kind == FileKind.ANNOTATED:
                record.uploaded_at = uploaded_at
            if payload.storage_last_modified is not None:
                record.storage_last_modified = payload.storage_last_modified
            self.record_repository.save(record)

        self.db.commit()
        self.db.refresh(file_object)
        return file_object

    def request_ai_review(self, record_id: int, payload: AIReviewRequest) -> dict:
        """触发 AI 复核预留接口。"""

        record = self.record_repository.get_by_id(record_id, include_related=False)
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        return self.ai_review_client.request_review(
            record_id=record_id,
            provider_hint=payload.provider_hint,
            note=payload.note,
        )
