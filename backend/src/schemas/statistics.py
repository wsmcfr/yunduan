"""统计接口 Schema。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


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
