"""审核路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.schemas.review import ManualReviewCreateRequest, ReviewListResponse, ReviewRecordResponse
from src.services.review_service import ReviewService

router = APIRouter()


@router.post("/records/{record_id}/manual-review", response_model=ReviewRecordResponse)
def create_manual_review(
    record_id: int,
    payload: ManualReviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewRecordResponse:
    """提交指定检测记录的人工审核结果。"""

    review = ReviewService(db).create_manual_review(
        record_id=record_id,
        reviewer_id=current_user.id,
        payload=payload,
    )
    return ReviewRecordResponse.model_validate(review)


@router.get("/records/{record_id}/reviews", response_model=ReviewListResponse)
def list_reviews(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ReviewListResponse:
    """获取指定检测记录的审核历史。"""

    reviews = ReviewService(db).list_reviews(record_id)
    return ReviewListResponse(
        items=[ReviewRecordResponse.model_validate(item) for item in reviews]
    )
