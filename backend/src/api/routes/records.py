"""检测记录路由。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.deps import (
    get_current_ai_enabled_user,
    get_current_company_admin_user,
    get_current_company_user,
    get_db,
)
from src.core.sse import build_sse_headers
from src.db.models.enums import DetectionResult, ReviewStatus
from src.db.models.user import User
from src.schemas.detection_record import (
    DetectionRecordCreateRequest,
    DetectionRecordDetailResponse,
    DetectionRecordListItem,
    DetectionRecordListResponse,
)
from src.schemas.common import ApiMessageResponse
from src.schemas.review import AIChatRequest, AIChatResponse, AIReviewRequest, AIReviewResponse
from src.schemas.upload import FileObjectCreateRequest, FileObjectResponse
from src.services.record_service import RecordService

router = APIRouter()


@router.get("", response_model=DetectionRecordListResponse)
def list_records(
    part_id: int | None = Query(default=None, ge=1),
    part_category: str | None = Query(default=None, min_length=1, max_length=64),
    device_id: int | None = Query(default=None, ge=1),
    result: DetectionResult | None = Query(default=None),
    review_status: ReviewStatus | None = Query(default=None),
    captured_from: datetime | None = Query(default=None),
    captured_to: datetime | None = Query(default=None),
    uploaded_from: datetime | None = Query(default=None),
    uploaded_to: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> DetectionRecordListResponse:
    """分页获取检测记录列表。"""

    total, items = RecordService(db).list_records(
        company_id=current_user.company_id or 0,
        part_id=part_id,
        part_category=part_category,
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
    return DetectionRecordListResponse(
        items=[DetectionRecordListItem.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=DetectionRecordDetailResponse)
def create_record(
    payload: DetectionRecordCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> DetectionRecordDetailResponse:
    """创建新的检测记录。"""

    record = RecordService(db).create_record(company_id=current_user.company_id or 0, payload=payload)
    return DetectionRecordDetailResponse.model_validate(record)


@router.get("/{record_id}", response_model=DetectionRecordDetailResponse)
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> DetectionRecordDetailResponse:
    """获取单条检测记录详情。"""

    record = RecordService(db).get_record_detail(
        company_id=current_user.company_id or 0,
        record_id=record_id,
    )
    return DetectionRecordDetailResponse.model_validate(record)


@router.delete("/{record_id}", response_model=ApiMessageResponse)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_admin_user),
) -> ApiMessageResponse:
    """删除单条检测记录及其关联文件、复核历史。"""

    RecordService(db).delete_record(
        company_id=current_user.company_id or 0,
        record_id=record_id,
    )
    return ApiMessageResponse(message="检测记录已删除。")


@router.post("/{record_id}/files", response_model=FileObjectResponse)
def create_file_object(
    record_id: int,
    payload: FileObjectCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> FileObjectResponse:
    """登记检测记录关联的文件对象。"""

    file_object = RecordService(db).create_file_object(
        company_id=current_user.company_id or 0,
        record_id=record_id,
        payload=payload,
    )
    return FileObjectResponse.model_validate(file_object)


@router.post("/{record_id}/ai-review", response_model=AIReviewResponse)
def request_ai_review(
    record_id: int,
    payload: AIReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_ai_enabled_user),
) -> AIReviewResponse:
    """触发 AI 复核预留接口。"""

    result = RecordService(db).request_ai_review(
        company_id=current_user.company_id or 0,
        record_id=record_id,
        payload=payload,
    )
    return AIReviewResponse.model_validate(result)


@router.post("/{record_id}/ai-chat", response_model=AIChatResponse)
def request_ai_chat(
    record_id: int,
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_ai_enabled_user),
) -> AIChatResponse:
    """在当前检测记录上下文下发起 AI 对话。"""

    result = RecordService(db).request_ai_chat(
        company_id=current_user.company_id or 0,
        record_id=record_id,
        payload=payload,
    )
    return AIChatResponse.model_validate(result)


@router.post("/{record_id}/ai-chat/stream")
def stream_ai_chat(
    record_id: int,
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_ai_enabled_user),
) -> StreamingResponse:
    """在当前检测记录上下文下发起流式 AI 对话。"""

    return StreamingResponse(
        RecordService(db).stream_ai_chat(
            company_id=current_user.company_id or 0,
            record_id=record_id,
            payload=payload,
        ),
        media_type="text/event-stream",
        headers=build_sse_headers(),
    )
