"""云端复核同步板端的服务测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.core.errors import BadRequestError
from src.db.base import Base
from src.db.models.company import Company
from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.enums import DetectionResult, DeviceStatus, DeviceType, ReviewStatus, UserRole
from src.db.models.file_object import FileObject
from src.db.models.part import Part
from src.db.models.review_record import ReviewRecord
from src.db.models.user import User
from src.schemas.review import BoardReviewSyncRequest
from src.services.review_service import ReviewService, map_cloud_result_to_board


class FakeBoardReviewClient:
    """记录服务向板端发出的同步请求，并返回预设结果。"""

    def __init__(self, *, ok: bool = True, error: str | None = None) -> None:
        """初始化伪客户端。

        参数:
            ok: 模拟板端是否同步成功。
            error: 模拟板端失败时返回的错误摘要。
        """

        self.ok = ok
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def post_review(
        self,
        *,
        url: str,
        token: str,
        payload: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """记录一次板端回写调用，并返回预设结果。"""

        self.calls.append(
            {
                "url": url,
                "token": token,
                "payload": payload,
            }
        )
        return self.ok, self.error


class ReviewServiceBoardSyncTestCase(unittest.TestCase):
    """验证云端复核同步板端的核心服务行为。"""

    def setUp(self) -> None:
        """为每个测试准备隔离的内存数据库和基础主数据。"""

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Company.__table__,
                User.__table__,
                Device.__table__,
                Part.__table__,
                DetectionRecord.__table__,
                FileObject.__table__,
                ReviewRecord.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.session_factory()
        self.company = self._create_company()
        self.reviewer = self._create_reviewer()
        self.device = self._create_device()
        self.part = self._create_part()

    def tearDown(self) -> None:
        """关闭数据库连接，避免测试之间共享状态。"""

        self.db.close()
        self.engine.dispose()

    def _create_company(self) -> Company:
        """创建测试公司，服务层所有查询都必须受公司边界约束。"""

        company = Company(
            name="板端同步测试公司",
            contact_name="测试联系人",
            note="用于板端同步服务测试。",
            invite_code="BOARDSYNC",
            is_active=True,
            is_system_reserved=False,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def _create_reviewer(self) -> User:
        """创建测试复核用户，响应层需要读取显示名称。"""

        user = User(
            username="admin",
            email="admin@example.com",
            password_hash="not-a-real-hash",
            password_changed_at=None,
            display_name="admin",
            role=UserRole.REVIEWER,
            company_id=self.company.id,
            is_default_admin=False,
            is_active=True,
            can_use_ai_analysis=False,
            last_login_at=None,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _create_device(
        self,
        *,
        board_review_url: str | None = "http://192.168.1.250:18080/api/v1/review-result",
        board_review_token: str | None = "board-token",
    ) -> Device:
        """创建带板端回写配置的 MP157 设备。"""

        device = Device(
            company_id=self.company.id,
            device_code="MP157-BOARD-SYNC-01",
            name="板端同步主控",
            device_type=DeviceType.MP157,
            status=DeviceStatus.ONLINE,
            firmware_version="2026.05.19",
            ip_address="192.168.1.250",
            last_seen_at=datetime(2026, 5, 19, 14, 0, 0, tzinfo=timezone.utc),
            board_review_url=board_review_url,
            board_review_token=board_review_token,
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def _create_part(self) -> Part:
        """创建真实零件类型，验证复核同步不创建按好坏拆分的零件。"""

        part = Part(
            company_id=self.company.id,
            part_code="gasket",
            name="密封垫",
            category="标准件",
            description=None,
            is_active=True,
        )
        self.db.add(part)
        self.db.commit()
        self.db.refresh(part)
        return part

    def _create_detection_record(self, *, result: DetectionResult = DetectionResult.GOOD) -> DetectionRecord:
        """创建一条待同步复核结果的检测记录。"""

        record = DetectionRecord(
            company_id=self.company.id,
            record_no="MP157-VIS-01-20260519-143012-0001",
            part_id=self.part.id,
            device_id=self.device.id,
            result=result,
            review_status=ReviewStatus.PENDING,
            surface_result=result,
            backlight_result=None,
            eddy_result=None,
            defect_type=None,
            defect_desc=None,
            confidence_score=0.96,
            vision_context=None,
            sensor_context=None,
            decision_context=None,
            device_context={"part_code": "gasket", "class_label": "gasket_good"},
            captured_at=datetime(2026, 5, 19, 14, 30, 12, tzinfo=timezone.utc),
            detected_at=None,
            uploaded_at=None,
            storage_last_modified=None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def test_map_cloud_result_to_board_converts_uncertain_to_review(self) -> None:
        """云端待复核结果发送给板端时必须转成板端接受的 review。"""

        self.assertEqual(map_cloud_result_to_board(DetectionResult.GOOD), "good")
        self.assertEqual(map_cloud_result_to_board(DetectionResult.BAD), "bad")
        self.assertEqual(map_cloud_result_to_board(DetectionResult.UNCERTAIN), "review")

    def test_sync_board_review_creates_review_and_posts_board_payload(self) -> None:
        """同步成功时，应创建云端复核记录并写入板端成功状态。"""

        record = self._create_detection_record(result=DetectionResult.GOOD)
        board_client = FakeBoardReviewClient()
        service = ReviewService(self.db, board_review_client=board_client)
        reviewed_at = datetime(2026, 5, 19, 14, 3, 10, tzinfo=timezone.utc)

        response = service.sync_board_review(
            company_id=self.company.id,
            record_id=record.id,
            reviewer_id=self.reviewer.id,
            reviewer_name="admin",
            payload=BoardReviewSyncRequest(
                decision=DetectionResult.BAD,
                cloud_reason="云端复核发现边缘划痕，板端原判良品需要修正。",
                defect_type="划痕",
                reviewed_at=reviewed_at,
            ),
        )

        persisted_record = self.db.get(DetectionRecord, record.id)
        reviews = list(
            self.db.execute(
                select(ReviewRecord).where(ReviewRecord.detection_record_id == record.id)
            ).scalars()
        )
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].comment, "云端复核发现边缘划痕，板端原判良品需要修正。")
        self.assertEqual(persisted_record.review_status, ReviewStatus.REVIEWED)
        self.assertEqual(persisted_record.board_sync_status, "success")
        self.assertIsNotNone(persisted_record.board_sync_time)
        self.assertIsNone(persisted_record.board_sync_error)
        self.assertEqual(persisted_record.board_last_synced_review_id, reviews[0].id)
        self.assertEqual(response.board_sync_status, "success")
        self.assertEqual(len(board_client.calls), 1)
        self.assertEqual(board_client.calls[0]["url"], "http://192.168.1.250:18080/api/v1/review-result")
        self.assertEqual(board_client.calls[0]["token"], "board-token")
        self.assertEqual(
            board_client.calls[0]["payload"],
            {
                "record_id": str(record.id),
                "record_no": "MP157-VIS-01-20260519-143012-0001",
                "cloud_result": "bad",
                "cloud_reason": "云端复核发现边缘划痕，板端原判良品需要修正。",
                "operator": "admin",
                "review_time": "2026-05-19 14:03:10",
                "source": "cloud",
            },
        )

    def test_sync_board_review_rejects_blank_reason_before_creating_review(self) -> None:
        """修正原因为空时，不应创建复核记录，也不应调用板端。"""

        record = self._create_detection_record()
        board_client = FakeBoardReviewClient()
        service = ReviewService(self.db, board_review_client=board_client)

        with self.assertRaises(BadRequestError) as caught:
            service.sync_board_review(
                company_id=self.company.id,
                record_id=record.id,
                reviewer_id=self.reviewer.id,
                reviewer_name="admin",
                payload=BoardReviewSyncRequest(
                    decision=DetectionResult.BAD,
                    cloud_reason="   ",
                    defect_type=None,
                    reviewed_at=None,
                ),
            )

        reviews = list(
            self.db.execute(
                select(ReviewRecord).where(ReviewRecord.detection_record_id == record.id)
            ).scalars()
        )
        self.assertEqual(caught.exception.code, "board_review_reason_required")
        self.assertEqual(reviews, [])
        self.assertEqual(board_client.calls, [])

    def test_sync_board_review_saves_failed_status_when_device_has_no_url(self) -> None:
        """未配置板端回写地址时，云端复核仍保留，但同步状态应为 failed。"""

        self.device.board_review_url = None
        self.db.commit()
        record = self._create_detection_record()
        board_client = FakeBoardReviewClient()
        service = ReviewService(self.db, board_review_client=board_client)

        response = service.sync_board_review(
            company_id=self.company.id,
            record_id=record.id,
            reviewer_id=self.reviewer.id,
            reviewer_name="admin",
            payload=BoardReviewSyncRequest(
                decision=DetectionResult.BAD,
                cloud_reason="云端确认坏品。",
                defect_type=None,
                reviewed_at=None,
            ),
        )

        persisted_record = self.db.get(DetectionRecord, record.id)
        self.assertEqual(persisted_record.board_sync_status, "failed")
        self.assertEqual(persisted_record.board_sync_error, "当前设备未配置板端回写地址。")
        self.assertEqual(response.board_sync_status, "failed")
        self.assertEqual(board_client.calls, [])

    def test_sync_board_review_saves_failed_status_when_device_has_no_token(self) -> None:
        """未配置板端回写密钥时，云端复核仍保留，但不应发起无鉴权请求。"""

        self.device.board_review_token = None
        self.db.commit()
        record = self._create_detection_record()
        board_client = FakeBoardReviewClient()
        service = ReviewService(self.db, board_review_client=board_client)

        response = service.sync_board_review(
            company_id=self.company.id,
            record_id=record.id,
            reviewer_id=self.reviewer.id,
            reviewer_name="admin",
            payload=BoardReviewSyncRequest(
                decision=DetectionResult.BAD,
                cloud_reason="云端确认坏品。",
                defect_type=None,
                reviewed_at=None,
            ),
        )

        persisted_record = self.db.get(DetectionRecord, record.id)
        self.assertEqual(persisted_record.board_sync_status, "failed")
        self.assertEqual(persisted_record.board_sync_error, "当前设备未配置板端回写密钥。")
        self.assertEqual(response.board_sync_status, "failed")
        self.assertEqual(board_client.calls, [])

    def test_sync_board_review_preserves_review_when_board_returns_error(self) -> None:
        """板端返回失败时，不应撤销云端复核，只记录失败摘要以便重试。"""

        record = self._create_detection_record()
        board_client = FakeBoardReviewClient(ok=False, error="板端密钥错误。")
        service = ReviewService(self.db, board_review_client=board_client)

        response = service.sync_board_review(
            company_id=self.company.id,
            record_id=record.id,
            reviewer_id=self.reviewer.id,
            reviewer_name="admin",
            payload=BoardReviewSyncRequest(
                decision=DetectionResult.UNCERTAIN,
                cloud_reason="云端无法确认，需要板端显示待复核。",
                defect_type=None,
                reviewed_at=datetime(2026, 5, 19, 14, 4, 0, tzinfo=timezone.utc),
            ),
        )

        persisted_record = self.db.get(DetectionRecord, record.id)
        reviews = list(
            self.db.execute(
                select(ReviewRecord).where(ReviewRecord.detection_record_id == record.id)
            ).scalars()
        )
        self.assertEqual(len(reviews), 1)
        self.assertEqual(persisted_record.board_sync_status, "failed")
        self.assertEqual(persisted_record.board_sync_error, "板端密钥错误。")
        self.assertEqual(response.board_sync_status, "failed")
        self.assertEqual(board_client.calls[0]["payload"]["cloud_result"], "review")


if __name__ == "__main__":
    unittest.main()
