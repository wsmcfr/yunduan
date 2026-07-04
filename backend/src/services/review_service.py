"""审核服务实现。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from src.core.errors import BadRequestError, NotFoundError
from src.core.logging import get_logger
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, ReviewSource, ReviewStatus
from src.db.models.review_record import ReviewRecord
from src.repositories.detection_record_repository import DetectionRecordRepository
from src.repositories.review_repository import ReviewRepository
from src.schemas.review import (
    BoardReviewSyncRequest,
    BoardReviewSyncResponse,
    ManualReviewCreateRequest,
    ReviewRecordResponse,
)

logger = get_logger(__name__)

BOARD_REVIEW_DISPLAY_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def format_board_review_time(reviewed_at: datetime) -> str:
    """把云端复核时间格式化为板端详情页显示的中国本地时间。

    云端数据库统一保存 UTC 时间，前端 `new Date().toISOString()` 也会提交 UTC ISO。
    板端 `review_time` 字段是无时区的可读字符串，如果直接使用云服务器本机时区，
    服务器运行在 UTC 时就会比现场时间少 8 小时。这里固定转成 UTC+8，保证云端
    修正后写回 MP157 的时间与操作员看到的中国本地时间一致。
    """

    if reviewed_at.tzinfo is None or reviewed_at.tzinfo.utcoffset(reviewed_at) is None:
        reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)
    return reviewed_at.astimezone(BOARD_REVIEW_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def map_cloud_result_to_board(decision: DetectionResult) -> str:
    """把云端检测结果枚举转换成板端回写接口接受的枚举。"""

    if decision == DetectionResult.UNCERTAIN:
        return "review"
    return decision.value


class BoardReviewClient:
    """负责调用 STM32MP157 板端复核结果回写接口。"""

    def post_review(
        self,
        *,
        url: str,
        token: str,
        payload: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """向板端发送云端复核结果，并返回是否成功和错误摘要。

        参数:
            url: 设备配置的板端完整回写地址。
            token: 设备配置的板端鉴权密钥。
            payload: 已按板端契约组装好的 JSON 请求体。

        返回:
            二元组，第一个值表示板端是否接受本次回写，第二个值是失败原因。
        """

        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"X-Board-Token": token},
                timeout=5.0,
            )
        except httpx.TimeoutException:
            return False, "连接板端超时，请检查开发板网络和回写地址。"
        except httpx.RequestError as exc:
            return False, f"连接板端失败：{exc}"

        if response.status_code == 401:
            return False, "板端密钥错误。"
        if response.status_code == 404:
            return False, "板端找不到对应检测记录，检查 record_id/record_no。"
        if response.status_code >= 400:
            return False, f"板端返回 HTTP {response.status_code}：{response.text[:300]}"

        try:
            body = response.json()
        except ValueError:
            return False, "板端返回内容不是有效 JSON。"

        if body.get("ok") is not True:
            return False, str(body.get("error") or body.get("message") or "板端返回失败。")

        return True, None


class ReviewService:
    """封装人工审核流程。"""

    def __init__(
        self,
        db: Session,
        board_review_client: BoardReviewClient | None = None,
    ) -> None:
        """初始化审核服务依赖。

        参数:
            db: 当前请求作用域数据库会话。
            board_review_client: 板端 HTTP 客户端；测试可注入伪客户端避免真实网络。
        """

        self.db = db
        self.record_repository = DetectionRecordRepository(db)
        self.review_repository = ReviewRepository(db)
        self.board_review_client = board_review_client or BoardReviewClient()

    def create_manual_review(
        self,
        *,
        company_id: int,
        record_id: int,
        reviewer_id: int,
        payload: ManualReviewCreateRequest,
    ) -> ReviewRecord:
        """为指定检测记录新增一条人工审核记录。"""

        record = self.record_repository.get_by_id(
            record_id,
            company_id=company_id,
            include_related=False,
        )
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        review = ReviewRecord(
            company_id=company_id,
            detection_record_id=record_id,
            reviewer_id=reviewer_id,
            review_source=ReviewSource.MANUAL,
            decision=payload.decision,
            defect_type=payload.defect_type,
            comment=payload.comment,
            reviewed_at=payload.reviewed_at or datetime.now(timezone.utc),
        )
        self.review_repository.create(review)
        record.review_status = ReviewStatus.REVIEWED
        self.record_repository.save(record)
        self.db.commit()
        self.db.refresh(review)
        logger.info(
            "record.review_completed event=record.review_completed record_id=%s reviewer_id=%s decision=%s",
            record_id,
            reviewer_id,
            review.decision.value,
        )
        return review

    def list_reviews(self, *, company_id: int, record_id: int) -> list[ReviewRecord]:
        """返回指定检测记录的全部审核记录。"""

        record = self.record_repository.get_by_id(
            record_id,
            company_id=company_id,
            include_related=False,
        )
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        return self.review_repository.list_by_record_id(record_id)

    def _validate_board_review_url(self, url: str) -> None:
        """校验板端回写 URL 至少是 HTTP/HTTPS 地址，降低误配和 SSRF 风险。"""

        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise BadRequestError(
                code="board_review_url_invalid",
                message="板端回写地址必须是有效的 http 或 https URL。",
            )

    def _create_sync_review(
        self,
        *,
        company_id: int,
        record_id: int,
        reviewer_id: int,
        payload: BoardReviewSyncRequest,
        cloud_reason: str,
    ) -> ReviewRecord:
        """创建云端人工复核记录，并把检测主记录标记为已复核。"""

        review = ReviewRecord(
            company_id=company_id,
            detection_record_id=record_id,
            reviewer_id=reviewer_id,
            review_source=ReviewSource.MANUAL,
            decision=payload.decision,
            defect_type=payload.defect_type,
            comment=cloud_reason,
            reviewed_at=payload.reviewed_at or datetime.now(timezone.utc),
        )
        self.review_repository.create(review)
        return review

    def _build_board_payload(
        self,
        *,
        record: DetectionRecord,
        review: ReviewRecord,
        reviewer_name: str,
    ) -> dict[str, Any]:
        """按板端 `/api/v1/review-result` 契约组装 JSON 请求体。"""

        return {
            "record_id": str(record.id),
            "record_no": record.record_no,
            "cloud_result": map_cloud_result_to_board(review.decision),
            "cloud_reason": review.comment or "",
            "operator": reviewer_name,
            "review_time": format_board_review_time(review.reviewed_at),
            "source": "cloud",
        }

    def _mark_board_sync_failed(
        self,
        *,
        record: DetectionRecord,
        error: str,
    ) -> None:
        """把检测记录标记为板端同步失败，并保存可读错误摘要。"""

        record.board_sync_status = "failed"
        record.board_sync_error = error
        self.record_repository.save(record)

    def _mark_board_sync_success(
        self,
        *,
        record: DetectionRecord,
        review: ReviewRecord,
    ) -> None:
        """把检测记录标记为板端同步成功，并记录对应复核记录。"""

        record.board_sync_status = "success"
        record.board_sync_time = datetime.now(timezone.utc)
        record.board_sync_error = None
        record.board_last_synced_review_id = review.id
        self.record_repository.save(record)

    def sync_board_review(
        self,
        *,
        company_id: int,
        record_id: int,
        reviewer_id: int,
        reviewer_name: str,
        payload: BoardReviewSyncRequest,
    ) -> BoardReviewSyncResponse:
        """提交云端复核结论，并把结论同步到板端本地历史。

        主要流程:
        1. 先按公司边界读取检测记录和关联设备。
        2. 校验修正原因不能为空，避免板端历史出现无依据改判。
        3. 创建云端人工复核记录，云端最终结论先落库。
        4. 使用设备上的板端回写配置调用开发板接口。
        5. 不论板端是否成功，都保留云端复核；失败只写同步失败状态供重试。
        """

        record = self.record_repository.get_by_id(
            record_id,
            company_id=company_id,
            include_related=True,
        )
        if record is None:
            raise NotFoundError(code="record_not_found", message="检测记录不存在。")

        cloud_reason = payload.cloud_reason.strip()
        if not cloud_reason:
            raise BadRequestError(
                code="board_review_reason_required",
                message="请填写修正原因。",
            )

        review = self._create_sync_review(
            company_id=company_id,
            record_id=record_id,
            reviewer_id=reviewer_id,
            payload=payload,
            cloud_reason=cloud_reason,
        )
        record.review_status = ReviewStatus.REVIEWED
        self.record_repository.save(record)
        self.db.commit()
        self.db.refresh(review)
        self.db.refresh(record)

        board_url = (record.device.board_review_url or "").strip() if record.device else ""
        board_token = (record.device.board_review_token or "").strip() if record.device else ""
        if not board_url:
            self._mark_board_sync_failed(record=record, error="当前设备未配置板端回写地址。")
            self.db.commit()
            self.db.refresh(record)
            return BoardReviewSyncResponse(
                review=ReviewRecordResponse.model_validate(review),
                board_sync_status=record.board_sync_status or "failed",
                board_sync_time=record.board_sync_time,
                board_sync_error=record.board_sync_error,
            )
        if not board_token:
            self._mark_board_sync_failed(record=record, error="当前设备未配置板端回写密钥。")
            self.db.commit()
            self.db.refresh(record)
            return BoardReviewSyncResponse(
                review=ReviewRecordResponse.model_validate(review),
                board_sync_status=record.board_sync_status or "failed",
                board_sync_time=record.board_sync_time,
                board_sync_error=record.board_sync_error,
            )

        self._validate_board_review_url(board_url)
        board_payload = self._build_board_payload(
            record=record,
            review=review,
            reviewer_name=reviewer_name,
        )
        ok, error = self.board_review_client.post_review(
            url=board_url,
            token=board_token,
            payload=board_payload,
        )
        if ok:
            self._mark_board_sync_success(record=record, review=review)
        else:
            self._mark_board_sync_failed(record=record, error=error or "板端返回失败。")

        self.db.commit()
        self.db.refresh(record)
        self.db.refresh(review)
        logger.info(
            "record.board_review_synced event=record.board_review_synced record_id=%s review_id=%s status=%s",
            record_id,
            review.id,
            record.board_sync_status,
        )
        return BoardReviewSyncResponse(
            review=ReviewRecordResponse.model_validate(review),
            board_sync_status=record.board_sync_status or "failed",
            board_sync_time=record.board_sync_time,
            board_sync_error=record.board_sync_error,
        )
