"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.db.models.user import User
from src.schemas.auth import LoginRequest, LoginResponse, UserProfile
from src.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """处理用户登录并返回 JWT 令牌。"""

    token, user = AuthService(db).login(payload.username, payload.password)
    return LoginResponse(
        access_token=token,
        user=UserProfile.model_validate(user),
    )


@router.get("/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    """返回当前登录用户信息。"""

    return UserProfile.model_validate(current_user)
