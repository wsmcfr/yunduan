"""审核相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.db.models.enums import DetectionResult, FileKind, ReviewSource, ReviewStatus
from src.schemas.common import ORMBaseModel


class ManualReviewCreateRequest(BaseModel):
    """人工审核提交请求体。"""

    decision: DetectionResult
    defect_type: str | None = Field(default=None, max_length=128)
    comment: str | None = None
    reviewed_at: datetime | None = None


class ReviewRecordResponse(ORMBaseModel):
    """审核记录响应体。"""

    id: int
    detection_record_id: int
    reviewer_id: int | None
    reviewer_display_name: str | None
    review_source: ReviewSource
    decision: DetectionResult
    defect_type: str | None
    comment: str | None
    reviewed_at: datetime
    created_at: datetime


class ReviewListResponse(BaseModel):
    """审核记录列表响应体。"""

    items: list[ReviewRecordResponse]


class AIReviewRequest(BaseModel):
    """AI 复核预留接口请求体。"""

    model_profile_id: int | None = Field(default=None, ge=1)
    provider_hint: str | None = Field(default=None, max_length=64)
    note: str | None = None


class AIReviewResponse(BaseModel):
    """AI 复核预留接口响应体。"""

    status: str
    message: str
    record_id: int


class AIChatHistoryMessage(BaseModel):
    """AI 对话历史消息。"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AIChatRequest(BaseModel):
    """AI 对话请求体。"""

    question: str = Field(min_length=1, max_length=2000)
    model_profile_id: int | None = Field(default=None, ge=1)
    provider_hint: str | None = Field(default=None, max_length=64)
    history: list[AIChatHistoryMessage] = Field(default_factory=list)


class AIContextFile(BaseModel):
    """AI 对话使用的文件上下文。"""

    id: int
    file_kind: FileKind
    bucket_name: str
    region: str
    object_key: str
    uploaded_at: datetime | None
    preview_url: str | None


class AIRecordContext(BaseModel):
    """AI 对话使用的检测记录上下文摘要。"""

    record_id: int
    record_no: str
    part_name: str
    part_code: str
    device_name: str
    device_code: str
    result: DetectionResult
    effective_result: DetectionResult
    review_status: ReviewStatus
    defect_type: str | None
    defect_desc: str | None
    confidence_score: float | None
    captured_at: datetime
    detected_at: datetime | None
    uploaded_at: datetime | None
    storage_last_modified: datetime | None
    file_count: int
    review_count: int
    available_file_kinds: list[FileKind]
    latest_review_decision: DetectionResult | None
    latest_review_comment: str | None
    latest_reviewed_at: datetime | None


class AIChatResponse(BaseModel):
    """AI 对话响应体。"""

    status: str
    answer: str
    record_id: int
    provider_hint: str | None = None
    context: AIRecordContext
    referenced_files: list[AIContextFile]
    suggested_questions: list[str]
