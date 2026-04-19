"""审核相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import DetectionResult, ReviewSource
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

    provider_hint: str | None = Field(default=None, max_length=64)
    note: str | None = None


class AIReviewResponse(BaseModel):
    """AI 复核预留接口响应体。"""

    status: str
    message: str
    record_id: int
