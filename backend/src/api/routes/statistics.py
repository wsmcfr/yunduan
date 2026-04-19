"""统计接口路由。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.schemas.statistics import (
    DailyTrendResponse,
    DefectDistributionResponse,
    SummaryStatisticsResponse,
)
from src.services.statistics_service import StatisticsService

router = APIRouter()


@router.get("/summary", response_model=SummaryStatisticsResponse)
def get_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SummaryStatisticsResponse:
    """返回检测结果概览统计。"""

    return StatisticsService(db).get_summary(start_date=start_date, end_date=end_date)


@router.get("/daily-trend", response_model=DailyTrendResponse)
def get_daily_trend(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DailyTrendResponse:
    """返回按天聚合的检测趋势统计。"""

    return StatisticsService(db).get_daily_trend(
        start_date=start_date,
        end_date=end_date,
        days=days,
    )


@router.get("/defect-distribution", response_model=DefectDistributionResponse)
def get_defect_distribution(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DefectDistributionResponse:
    """返回缺陷类型分布统计。"""

    return StatisticsService(db).get_defect_distribution(
        start_date=start_date,
        end_date=end_date,
    )
