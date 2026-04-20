"""检测记录服务实现。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy.orm import Session

from src.core.errors import AppError, ConflictError, NotFoundError
from src.core.logging import get_logger
from src.core.sse import build_sse_error_payload, format_sse_event
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, FileKind, ReviewStatus
from src.db.models.file_object import FileObject
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.repositories.device_repository import DeviceRepository
from src.repositories.part_repository import PartRepository
from src.schemas.detection_record import DetectionRecordCreateRequest
from src.schemas.review import AIChatRequest, AIReviewRequest
from src.schemas.upload import FileObjectCreateRequest
from src.integrations.ai_review_client import AIReviewClient
from src.integrations.cos_client import CosClient
from src.services.ai_gateway_service import AIGatewayService

logger = get_logger(__name__)


class RecordService:
    """封装检测记录创建、查询、文件登记和 AI 预留流程。"""

    _ai_file_priority = {
        FileKind.ANNOTATED: 0,
        FileKind.SOURCE: 1,
        FileKind.THUMBNAIL: 2,
    }

    def __init__(self, db: Session) -> None:
        """初始化检测记录服务依赖。"""

        self.db = db
        self.record_repository = DetectionRecordRepository(db)
        self.part_repository = PartRepository(db)
        self.device_repository = DeviceRepository(db)
        self.ai_review_client = AIReviewClient()
        self.cos_client = CosClient()

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
            vision_context=payload.vision_context,
            sensor_context=payload.sensor_context,
            decision_context=payload.decision_context,
            device_context=payload.device_context,
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

        # 详情接口需要直接把可预览地址带给前端。
        # 当前 COS 为私有桶时，前端自行拼接公网 URL 会被拒绝，因此这里统一生成带时效的访问地址。
        for file_object in record.files:
            file_object.preview_url = self._build_file_preview_url(file_object=file_object)

        return record

    def _build_file_preview_url(self, *, file_object: FileObject) -> str | None:
        """为图像对象生成可供前端预览或后续多模态接入使用的 URL。"""

        return self.cos_client.build_object_access_url(
            bucket_name=file_object.bucket_name,
            region=file_object.region,
            object_key=file_object.object_key,
        )

    def _select_ai_reference_files(self, *, record: DetectionRecord) -> list[FileObject]:
        """为 AI 对话挑选最有代表性的文件对象。"""

        return sorted(
            record.files,
            key=lambda item: (
                self._ai_file_priority.get(item.file_kind, 99),
                -(item.uploaded_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
                -item.id,
            ),
        )[:3]

    def _build_ai_chat_context(self, *, record: DetectionRecord) -> dict:
        """将检测记录转换成 AI 对话接口可直接消费的上下文字典。"""

        latest_review = record.latest_review
        available_file_kinds = list(dict.fromkeys([item.file_kind.value for item in record.files]))

        return {
            "record_id": record.id,
            "record_no": record.record_no,
            "part_name": record.part.name,
            "part_code": record.part.part_code,
            "part_category": record.part.category,
            "device_name": record.device.name,
            "device_code": record.device.device_code,
            "result": record.result.value,
            "effective_result": record.effective_result.value,
            "review_status": record.review_status.value,
            "defect_type": record.defect_type,
            "defect_desc": record.defect_desc,
            "confidence_score": record.confidence_score,
            "vision_context": record.vision_context,
            "sensor_context": record.sensor_context,
            "decision_context": record.decision_context,
            "device_context": record.device_context,
            "captured_at": record.captured_at,
            "detected_at": record.detected_at,
            "uploaded_at": record.uploaded_at,
            "storage_last_modified": record.storage_last_modified,
            "file_count": len(record.files),
            "review_count": len(record.reviews),
            "available_file_kinds": available_file_kinds,
            "latest_review_decision": latest_review.decision.value if latest_review is not None else None,
            "latest_review_comment": latest_review.comment if latest_review is not None else None,
            "latest_reviewed_at": latest_review.reviewed_at if latest_review is not None else None,
        }

    def _build_ai_referenced_files(self, *, record: DetectionRecord) -> list[dict]:
        """将 AI 对话中要引用的文件对象转换成稳定的响应结构。"""

        referenced_files: list[dict] = []

        for file_object in self._select_ai_reference_files(record=record):
            referenced_files.append(
                {
                    "id": file_object.id,
                    "file_kind": file_object.file_kind.value,
                    "bucket_name": file_object.bucket_name,
                    "region": file_object.region,
                    "object_key": file_object.object_key,
                    "uploaded_at": file_object.uploaded_at,
                    "preview_url": self._build_file_preview_url(file_object=file_object),
                }
            )

        return referenced_files

    def _resolve_runtime_model_context(self, model_profile_id: int | None) -> dict | None:
        """把前端选择的模型配置解析成运行时上下文摘要。"""

        if model_profile_id is None:
            return None

        return AIGatewayService(self.db).build_runtime_model_context(model_profile_id)

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
        # 新建文件对象后立即补上预览地址，保证单条文件登记接口与详情接口的返回结构一致。
        file_object.preview_url = self._build_file_preview_url(file_object=file_object)
        return file_object

    def request_ai_review(self, record_id: int, payload: AIReviewRequest) -> dict:
        """触发 AI 复核接口。"""

        record = self.get_record_detail(record_id)

        model_context = self._resolve_runtime_model_context(payload.model_profile_id)
        provider_hint = payload.provider_hint or (
            f"{model_context['gateway_name']} / {model_context['display_name']}"
            if model_context is not None
            else None
        )
        context = self._build_ai_chat_context(record=record)
        referenced_files = self._build_ai_referenced_files(record=record)

        return self.ai_review_client.request_review(
            record_id=record_id,
            provider_hint=provider_hint,
            note=payload.note,
            context=context,
            referenced_files=referenced_files,
            model_context=model_context,
        )

    def request_ai_chat(self, record_id: int, payload: AIChatRequest) -> dict:
        """在当前检测记录上下文下发起 AI 对话。"""

        record = self.get_record_detail(record_id)
        context = self._build_ai_chat_context(record=record)
        referenced_files = self._build_ai_referenced_files(record=record)
        model_context = self._resolve_runtime_model_context(payload.model_profile_id)
        provider_hint = payload.provider_hint or (
            f"{model_context['gateway_name']} / {model_context['display_name']}"
            if model_context is not None
            else None
        )

        return self.ai_review_client.chat_about_record(
            record_id=record_id,
            provider_hint=provider_hint,
            question=payload.question,
            history=[item.model_dump() for item in payload.history],
            context=context,
            referenced_files=referenced_files,
            model_context=model_context,
        )

    def stream_ai_chat(self, record_id: int, payload: AIChatRequest) -> Iterator[str]:
        """在当前检测记录上下文下以 SSE 方式流式返回 AI 对话结果。"""

        record = self.get_record_detail(record_id)
        context = self._build_ai_chat_context(record=record)
        referenced_files = self._build_ai_referenced_files(record=record)
        model_context = self._resolve_runtime_model_context(payload.model_profile_id)
        provider_hint = payload.provider_hint or (
            f"{model_context['gateway_name']} / {model_context['display_name']}"
            if model_context is not None
            else None
        )
        suggested_questions = self.ai_review_client.build_suggested_questions_for_context(
            context=context,
        )
        history = [item.model_dump() for item in payload.history]

        def event_stream() -> Iterator[str]:
            """封装单条记录对话的 SSE 事件序列。"""

            try:
                started_at = datetime.now(timezone.utc).isoformat()
                initial_status = "streaming" if model_context is not None else "contextual_response"
                meta_payload = {
                    "status": initial_status,
                    "answer": "",
                    "record_id": record_id,
                    "provider_hint": provider_hint,
                    "context": context,
                    "referenced_files": referenced_files,
                    "suggested_questions": suggested_questions,
                    "generated_at": started_at,
                }
                yield format_sse_event(event="meta", payload=meta_payload)

                if model_context is None:
                    response_payload = self.ai_review_client.chat_about_record(
                        record_id=record_id,
                        provider_hint=provider_hint,
                        question=payload.question,
                        history=history,
                        context=context,
                        referenced_files=referenced_files,
                        model_context=None,
                    )
                    answer_text = str(response_payload["answer"])
                    for text_chunk in self.ai_review_client._iter_text_chunks(text=answer_text):
                        yield format_sse_event(event="delta", payload={"text": text_chunk})

                    yield format_sse_event(event="done", payload=response_payload)
                    return

                answer_chunks: list[str] = []
                for text_chunk in self.ai_review_client.stream_chat_about_record(
                    record_id=record_id,
                    provider_hint=provider_hint,
                    question=payload.question,
                    history=history,
                    context=context,
                    referenced_files=referenced_files,
                    model_context=model_context,
                ):
                    answer_chunks.append(text_chunk)
                    yield format_sse_event(event="delta", payload={"text": text_chunk})

                yield format_sse_event(
                    event="done",
                    payload={
                        "status": "completed",
                        "answer": "".join(answer_chunks),
                        "record_id": record_id,
                        "provider_hint": provider_hint,
                        "context": context,
                        "referenced_files": referenced_files,
                        "suggested_questions": suggested_questions,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except AppError as exc:
                logger.warning(
                    "record.ai_chat_stream_failed event=record.ai_chat_stream_failed record_id=%s code=%s",
                    record_id,
                    exc.code,
                )
                yield format_sse_event(
                    event="error",
                    payload=build_sse_error_payload(exc),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "record.ai_chat_stream_unhandled event=record.ai_chat_stream_unhandled record_id=%s",
                    record_id,
                )
                yield format_sse_event(
                    event="error",
                    payload={
                        "status_code": 500,
                        "code": "stream_internal_error",
                        "message": "AI 对话流式输出过程中发生未处理错误。",
                        "details": {"reason": str(exc)},
                    },
                )

        return event_stream()
