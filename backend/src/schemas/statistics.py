"""统计接口 Schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.db.models.enums import DetectionResult, FileKind, ReviewStatus


class SummaryStatisticsResponse(BaseModel):
    """统计概览响应体。"""

    total_count: int
    good_count: int
    bad_count: int
    uncertain_count: int
    reviewed_count: int
    pending_review_count: int
    pass_rate: float


class DailyTrendItem(BaseModel):
    """每日趋势项。"""

    date: date
    total_count: int
    good_count: int
    bad_count: int
    uncertain_count: int


class DailyTrendResponse(BaseModel):
    """每日趋势响应体。"""

    items: list[DailyTrendItem]


class DefectDistributionItem(BaseModel):
    """缺陷分布项。"""

    defect_type: str
    count: int


class DefectDistributionResponse(BaseModel):
    """缺陷分布响应体。"""

    items: list[DefectDistributionItem]


class ResultDistributionItem(BaseModel):
    """最终结果分布项。"""

    result: DetectionResult
    count: int


class ReviewStatusDistributionItem(BaseModel):
    """审核状态分布项。"""

    review_status: ReviewStatus
    count: int


class PartQualityItem(BaseModel):
    """按零件聚合的质量统计项。"""

    part_id: int
    part_code: str
    part_name: str
    total_count: int
    good_count: int
    bad_count: int
    uncertain_count: int
    pass_rate: float


class DeviceQualityItem(BaseModel):
    """按设备聚合的质量统计项。"""

    device_id: int
    device_code: str
    device_name: str
    total_count: int
    good_count: int
    bad_count: int
    uncertain_count: int
    pass_rate: float


class StatisticsFiltersResponse(BaseModel):
    """统计页当前应用的过滤条件快照。"""

    start_date: date | None
    end_date: date | None
    days: int
    part_id: int | None
    device_id: int | None


class StatisticsSampleImageItem(BaseModel):
    """ç»Ÿè®¡é¡µå›¾åº“ä¸­çš„å•æ¡æ ·æœ¬é¡¹ã€‚"""

    record_id: int
    record_no: str
    part_id: int
    part_code: str
    part_name: str
    part_category: str | None
    device_id: int
    device_code: str
    device_name: str
    image_file_id: int | None
    image_file_kind: FileKind | None
    image_count: int
    preview_url: str | None
    uploaded_at: datetime | None
    captured_at: datetime
    effective_result: DetectionResult
    review_status: ReviewStatus
    defect_type: str | None
    defect_desc: str | None


class StatisticsPartImageGroup(BaseModel):
    """æŒ‰é›¶ä»¶å½’ç±»çš„å›¾åº“åˆ†ç»„ã€‚"""

    part_id: int
    part_code: str
    part_name: str
    part_category: str | None
    record_count: int
    image_count: int
    latest_uploaded_at: datetime | None
    items: list[StatisticsSampleImageItem]


class StatisticsSampleGalleryResponse(BaseModel):
    """ç»Ÿè®¡é¡µå›¾åº“åŒºåŸŸçš„æ±‡æ€»å“åº”ã€‚"""

    total_record_count: int
    total_image_count: int
    total_part_count: int
    latest_uploaded_at: datetime | None
    groups: list[StatisticsPartImageGroup]


class StatisticsOverviewResponse(BaseModel):
    """统计页所需的完整聚合响应。"""

    filters: StatisticsFiltersResponse
    summary: SummaryStatisticsResponse
    daily_trend: list[DailyTrendItem]
    defect_distribution: list[DefectDistributionItem]
    result_distribution: list[ResultDistributionItem]
    review_status_distribution: list[ReviewStatusDistributionItem]
    part_quality_ranking: list[PartQualityItem]
    device_quality_ranking: list[DeviceQualityItem]
    key_findings: list[str]
    sample_gallery: StatisticsSampleGalleryResponse
    generated_at: datetime


class StatisticsAIAnalysisRequest(BaseModel):
    """统计页 AI 分析请求体。"""

    model_profile_id: int | None = Field(default=None, ge=1)
    provider_hint: str | None = Field(default=None, max_length=64)
    note: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: int = Field(default=7, ge=1, le=90)
    part_id: int | None = Field(default=None, ge=1)
    device_id: int | None = Field(default=None, ge=1)


class StatisticsAIAnalysisResponse(BaseModel):
    """统计页 AI 分析响应体。"""

    status: str
    answer: str
    provider_hint: str | None = None
    generated_at: datetime


class StatisticsAIChatHistoryMessage(BaseModel):
    """统计页 AI 多轮追问中的单条历史消息。"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class StatisticsAIChatRequest(BaseModel):
    """统计页 AI 多轮追问请求体。"""

    question: str = Field(min_length=1, max_length=2000)
    model_profile_id: int | None = Field(default=None, ge=1)
    provider_hint: str | None = Field(default=None, max_length=64)
    note: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: int = Field(default=7, ge=1, le=90)
    part_id: int | None = Field(default=None, ge=1)
    device_id: int | None = Field(default=None, ge=1)
    history: list[StatisticsAIChatHistoryMessage] = Field(default_factory=list)


class StatisticsAIChatResponse(BaseModel):
    """统计页 AI 多轮追问响应体。"""

    status: str
    answer: str
    provider_hint: str | None = None
    generated_at: datetime
    suggested_questions: list[str]


class StatisticsExportConversationMessage(BaseModel):
    """统计导出时携带的 AI 工作台对话快照。"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    created_at: datetime | None = None


class StatisticsExportPdfRequest(BaseModel):
    """统计页服务端 PDF 导出请求体。"""

    export_mode: Literal["visual", "lightweight"] = "visual"
    model_profile_id: int | None = Field(default=None, ge=1)
    provider_hint: str | None = Field(default=None, max_length=64)
    note: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: int = Field(default=7, ge=1, le=90)
    part_id: int | None = Field(default=None, ge=1)
    device_id: int | None = Field(default=None, ge=1)
    include_ai_analysis: bool = True
    cached_ai_answer: str | None = None
    cached_ai_provider_hint: str | None = Field(default=None, max_length=128)
    cached_ai_generated_at: datetime | None = None
    cached_ai_conversation: list[StatisticsExportConversationMessage] = Field(default_factory=list)
    include_sample_images: bool = True
    sample_image_limit: int = Field(default=4, ge=0, le=8)
