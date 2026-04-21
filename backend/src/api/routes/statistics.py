"""统计接口路由。"""

from __future__ import annotations

from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.deps import get_current_ai_enabled_user, get_current_company_user, get_db
from src.core.sse import build_sse_headers
from src.db.models.user import User
from src.schemas.statistics import (
    DailyTrendResponse,
    DefectDistributionResponse,
    StatisticsAIAnalysisRequest,
    StatisticsAIAnalysisResponse,
    StatisticsExportPdfRequest,
    StatisticsSampleGalleryResponse,
    StatisticsOverviewResponse,
    SummaryStatisticsResponse,
)
from src.services.statistics_export_service import StatisticsExportService
from src.services.statistics_service import StatisticsService

router = APIRouter()


@router.get("/overview", response_model=StatisticsOverviewResponse)
def get_statistics_overview(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    part_id: int | None = Query(default=None, ge=1),
    device_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> StatisticsOverviewResponse:
    """返回统计页完整概览数据。"""

    return StatisticsService(db).get_overview(
        company_id=current_user.company_id or 0,
        start_date=start_date,
        end_date=end_date,
        days=days,
        part_id=part_id,
        device_id=device_id,
    )


@router.get("/sample-gallery", response_model=StatisticsSampleGalleryResponse)
def get_statistics_sample_gallery(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    part_id: int | None = Query(default=None, ge=1),
    part_category: str | None = Query(default=None, min_length=1, max_length=64),
    device_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> StatisticsSampleGalleryResponse:
    """返回独立图库页使用的分类样本图数据。"""

    return StatisticsService(db).get_sample_gallery(
        company_id=current_user.company_id or 0,
        start_date=start_date,
        end_date=end_date,
        days=days,
        part_id=part_id,
        part_category=part_category,
        device_id=device_id,
    )


@router.get("/summary", response_model=SummaryStatisticsResponse)
def get_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> SummaryStatisticsResponse:
    """返回检测结果概览统计。"""

    return StatisticsService(db).get_summary(
        company_id=current_user.company_id or 0,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/daily-trend", response_model=DailyTrendResponse)
def get_daily_trend(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> DailyTrendResponse:
    """返回按天聚合的检测趋势统计。"""

    return StatisticsService(db).get_daily_trend(
        company_id=current_user.company_id or 0,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )


@router.get("/defect-distribution", response_model=DefectDistributionResponse)
def get_defect_distribution(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> DefectDistributionResponse:
    """返回缺陷类型分布统计。"""

    return StatisticsService(db).get_defect_distribution(
        company_id=current_user.company_id or 0,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/ai-analysis", response_model=StatisticsAIAnalysisResponse)
def request_statistics_ai_analysis(
    payload: StatisticsAIAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_ai_enabled_user),
) -> StatisticsAIAnalysisResponse:
    """触发统计页 AI 批次分析。"""

    return StatisticsService(db).request_ai_analysis(
        company_id=current_user.company_id or 0,
        payload=payload,
    )


@router.post("/ai-analysis/stream")
def stream_statistics_ai_analysis(
    payload: StatisticsAIAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_ai_enabled_user),
) -> StreamingResponse:
    """流式触发统计页 AI 批次分析。"""

    return StreamingResponse(
        StatisticsService(db).stream_ai_analysis(
            company_id=current_user.company_id or 0,
            payload=payload,
        ),
        media_type="text/event-stream",
        headers=build_sse_headers(),
    )


@router.post("/export-pdf")
def export_statistics_pdf(
    payload: StatisticsExportPdfRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> StreamingResponse:
    """导出服务端生成的统计 PDF 报表。"""

    pdf_bytes, filename = StatisticsExportService(db).build_pdf(
        company_id=current_user.company_id or 0,
        payload=payload,
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
