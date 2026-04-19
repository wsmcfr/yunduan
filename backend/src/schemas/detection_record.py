"""检测记录相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import DetectionResult, ReviewStatus
from src.schemas.common import ORMBaseModel
from src.schemas.device import DeviceBrief
from src.schemas.part import PartBrief
from src.schemas.review import ReviewRecordResponse
from src.schemas.upload import FileObjectResponse


class DetectionRecordCreateRequest(BaseModel):
    """创建检测记录请求体。"""

    record_no: str | None = Field(default=None, max_length=64)
    part_id: int = Field(ge=1)
    device_id: int = Field(ge=1)
    result: DetectionResult
    review_status: ReviewStatus = ReviewStatus.PENDING
    surface_result: DetectionResult | None = None
    backlight_result: DetectionResult | None = None
    eddy_result: DetectionResult | None = None
    defect_type: str | None = Field(default=None, max_length=128)
    defect_desc: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    captured_at: datetime
    detected_at: datetime | None = None
    uploaded_at: datetime | None = None
    storage_last_modified: datetime | None = None


class DetectionRecordListItem(ORMBaseModel):
    """检测记录列表项响应体。"""

    id: int
    record_no: str
    part_id: int
    device_id: int
    result: DetectionResult
    effective_result: DetectionResult
    review_status: ReviewStatus
    surface_result: DetectionResult | None
    backlight_result: DetectionResult | None
    eddy_result: DetectionResult | None
    defect_type: str | None
    defect_desc: str | None
    confidence_score: float | None
    captured_at: datetime
    detected_at: datetime | None
    uploaded_at: datetime | None
    storage_last_modified: datetime | None
    created_at: datetime
    updated_at: datetime
    part: PartBrief
    device: DeviceBrief


class DetectionRecordDetailResponse(DetectionRecordListItem):
    """检测记录详情响应体。"""

    files: list[FileObjectResponse]
    reviews: list[ReviewRecordResponse]


class DetectionRecordListResponse(BaseModel):
    """检测记录列表响应体。"""

    items: list[DetectionRecordListItem]
    total: int
    skip: int
    limit: int
