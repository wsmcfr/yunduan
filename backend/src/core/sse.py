"""SSE 流式响应辅助函数。"""

from __future__ import annotations

import json
from typing import Any

from fastapi.encoders import jsonable_encoder

from src.core.errors import AppError


def build_sse_headers() -> dict[str, str]:
    """返回适用于 SSE 的响应头。

    这里显式关闭缓存和 Nginx 代理缓冲，避免浏览器要等很久才看到首个增量片段。
    """

    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def format_sse_event(*, event: str, payload: dict[str, Any]) -> str:
    """把单个事件编码成标准 SSE 文本块。"""

    serialized_payload = json.dumps(jsonable_encoder(payload), ensure_ascii=False)
    return f"event: {event}\ndata: {serialized_payload}\n\n"


def build_sse_error_payload(error: AppError) -> dict[str, Any]:
    """把服务层错误转换成前端可统一处理的流式错误载荷。"""

    return {
        "status_code": error.status_code,
        "code": error.code,
        "message": error.message,
        "details": error.details,
    }
