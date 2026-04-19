"""API 总路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routes import auth, devices, parts, records, reviews, statistics, uploads

# 顶层路由负责汇总所有业务子模块路由。
api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(parts.router, prefix="/parts", tags=["parts"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(records.router, prefix="/records", tags=["records"])
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(statistics.router, prefix="/statistics", tags=["statistics"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
