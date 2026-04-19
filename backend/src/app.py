"""FastAPI 应用入口。"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.router import api_router
from src.core.config import get_settings
from src.core.errors import AppError
from src.core.logging import get_logger, setup_logging

# 启动阶段先初始化日志，确保后续中间件和异常处理可用。
setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""

    app = FastAPI(
        title="云端检测系统 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        """为每个请求生成 request_id 并记录耗时。"""

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request.unhandled request_id=%s path=%s", request_id, request.url.path)
            raise

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        response.headers["X-Request-Id"] = request_id
        logger.info(
            "request.completed request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """将业务错误统一转换为结构化响应。"""

        request_id = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            },
        )

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        """提供基础健康检查接口。"""

        return {"status": "ok"}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
