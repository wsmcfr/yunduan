"""上传预留接口路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_company_user, get_db
from src.db.models.user import User
from src.schemas.upload import CosUploadPrepareRequest, CosUploadPrepareResponse
from src.services.upload_service import UploadService

router = APIRouter()


@router.post("/cos/prepare", response_model=CosUploadPrepareResponse)
def prepare_cos_upload(
    payload: CosUploadPrepareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_company_user),
) -> CosUploadPrepareResponse:
    """生成 COS 上传计划或占位结果。"""

    return UploadService(db).prepare_cos_upload(
        company_id=current_user.company_id or 0,
        payload=payload,
    )
