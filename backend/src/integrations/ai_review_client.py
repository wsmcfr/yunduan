"""AI 复核集成占位客户端。"""

from __future__ import annotations

from src.core.logging import get_logger

logger = get_logger(__name__)


class AIReviewClient:
    """当前版本仅保留 AI 复核集成边界，不做真实调用。"""

    def request_review(self, *, record_id: int, provider_hint: str | None, note: str | None) -> dict:
        """返回 AI 复核预留状态，供前后端先完成接口联调。"""

        logger.info(
            "ai_review.reserved event=ai_review.reserved record_id=%s provider_hint=%s",
            record_id,
            provider_hint or "",
        )
        return {
            "status": "reserved",
            "message": "AI 大模型复核接口已预留，当前版本未接入真实供应商。",
            "record_id": record_id,
            "provider_hint": provider_hint,
            "note": note,
        }
