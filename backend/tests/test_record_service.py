"""检测记录服务删除行为回归测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.core.errors import NotFoundError
from src.db.base import Base
from src.db.models.company import Company
from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.enums import (
    DetectionResult,
    DeviceStatus,
    DeviceType,
    FileKind,
    ReviewSource,
    ReviewStatus,
    StorageProvider,
)
from src.db.models.file_object import FileObject
from src.db.models.part import Part
from src.db.models.review_record import ReviewRecord
from src.services.record_service import RecordService


class FakeCosClient:
    """记录检测记录删除期间请求清理的 COS 对象。"""

    def __init__(self) -> None:
        """初始化已删除对象列表。"""

        self.deleted_objects: list[tuple[str, str, str]] = []

    def delete_object(self, *, bucket_name: str, region: str, object_key: str) -> None:
        """记录一次对象删除请求，避免单测触发真实云端调用。"""

        self.deleted_objects.append((bucket_name, region, object_key))


class RecordServiceTestCase(unittest.TestCase):
    """验证管理员删除单条检测记录时的聚合清理行为。"""

    def setUp(self) -> None:
        """为每个测试准备只包含记录删除所需表结构的内存数据库。"""

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Company.__table__,
                Device.__table__,
                Part.__table__,
                DetectionRecord.__table__,
                FileObject.__table__,
                ReviewRecord.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.session_factory()
        self.cos_client = FakeCosClient()
        self.service = RecordService(self.db, cos_client=self.cos_client)
        self.company = self._create_company()
        self.device = self._create_device()
        self.part = self._create_part()

    def tearDown(self) -> None:
        """释放测试数据库连接，避免测试之间互相污染。"""

        self.db.close()
        self.engine.dispose()

    def _create_company(self) -> Company:
        """创建标准测试公司，检测记录必须归属到该公司。"""

        company = Company(
            name="记录删除测试公司",
            contact_name="测试联系人",
            note="用于记录删除服务测试。",
            invite_code="RECDEL",
            is_active=True,
            is_system_reserved=False,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def _create_device(self) -> Device:
        """创建一台 MP157 设备，供检测记录引用。"""

        device = Device(
            company_id=self.company.id,
            device_code="MP157-REC-DELETE-01",
            name="记录删除测试主控",
            device_type=DeviceType.MP157,
            status=DeviceStatus.ONLINE,
            firmware_version=None,
            ip_address=None,
            last_seen_at=None,
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def _create_part(self) -> Part:
        """创建检测记录引用的零件类型。"""

        part = Part(
            company_id=self.company.id,
            part_code="PART-REC-DELETE-01",
            name="记录删除测试零件",
            category="测试",
            description=None,
            is_active=True,
        )
        self.db.add(part)
        self.db.commit()
        self.db.refresh(part)
        return part

    def _create_detection_record(self, *, record_no: str = "REC-DELETE-0001") -> DetectionRecord:
        """创建一条待删除的检测记录。"""

        record = DetectionRecord(
            company_id=self.company.id,
            record_no=record_no,
            part_id=self.part.id,
            device_id=self.device.id,
            result=DetectionResult.BAD,
            review_status=ReviewStatus.REVIEWED,
            surface_result=DetectionResult.BAD,
            backlight_result=None,
            eddy_result=None,
            defect_type="划痕",
            defect_desc=None,
            confidence_score=0.82,
            vision_context=None,
            sensor_context=None,
            decision_context=None,
            device_context=None,
            captured_at=datetime(2026, 5, 8, 9, 0, 0, tzinfo=timezone.utc),
            detected_at=None,
            uploaded_at=None,
            storage_last_modified=None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _create_record_file(self, *, record: DetectionRecord, object_key: str) -> FileObject:
        """创建检测记录文件对象，验证删除记录会同步清理图片元数据。"""

        file_object = FileObject(
            company_id=self.company.id,
            detection_record_id=record.id,
            file_kind=FileKind.SOURCE,
            storage_provider=StorageProvider.COS,
            bucket_name="demo-bucket",
            region="ap-shanghai",
            object_key=object_key,
            content_type="image/jpeg",
            size_bytes=2048,
            etag=None,
            uploaded_at=datetime(2026, 5, 8, 9, 1, 0, tzinfo=timezone.utc),
            storage_last_modified=None,
        )
        self.db.add(file_object)
        self.db.commit()
        self.db.refresh(file_object)
        return file_object

    def _create_record_review(self, *, record: DetectionRecord) -> ReviewRecord:
        """创建检测记录复核历史，验证删除记录会同步清理审核记录。"""

        review = ReviewRecord(
            company_id=self.company.id,
            detection_record_id=record.id,
            reviewer_id=None,
            review_source=ReviewSource.MANUAL,
            decision=DetectionResult.BAD,
            defect_type="划痕",
            comment="确认缺陷",
            reviewed_at=datetime(2026, 5, 8, 9, 2, 0, tzinfo=timezone.utc),
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def test_delete_record_purges_files_reviews_and_cos_objects(self) -> None:
        """删除检测记录时，应一并清理文件元数据、复核历史和 COS 对象。"""

        record = self._create_detection_record()
        first_file = self._create_record_file(record=record, object_key="detections/record/source.jpg")
        duplicated_file = self._create_record_file(record=record, object_key="detections/record/source.jpg")
        review = self._create_record_review(record=record)
        record_id = record.id
        first_file_id = first_file.id
        duplicated_file_id = duplicated_file.id
        review_id = review.id

        self.service.delete_record(company_id=self.company.id, record_id=record_id)

        persisted_record = self.db.scalar(select(DetectionRecord).where(DetectionRecord.id == record_id))
        persisted_first_file = self.db.scalar(select(FileObject).where(FileObject.id == first_file_id))
        persisted_duplicated_file = self.db.scalar(select(FileObject).where(FileObject.id == duplicated_file_id))
        persisted_review = self.db.scalar(select(ReviewRecord).where(ReviewRecord.id == review_id))
        persisted_part = self.db.scalar(select(Part).where(Part.id == self.part.id))
        persisted_device = self.db.scalar(select(Device).where(Device.id == self.device.id))
        self.assertIsNone(persisted_record)
        self.assertIsNone(persisted_first_file)
        self.assertIsNone(persisted_duplicated_file)
        self.assertIsNone(persisted_review)
        self.assertIsNotNone(persisted_part)
        self.assertIsNotNone(persisted_device)
        self.assertEqual(
            self.cos_client.deleted_objects,
            [("demo-bucket", "ap-shanghai", "detections/record/source.jpg")],
        )

    def test_delete_record_rejects_missing_record(self) -> None:
        """删除不存在或不属于当前公司的检测记录时，应返回不存在错误。"""

        with self.assertRaises(NotFoundError) as caught:
            self.service.delete_record(company_id=self.company.id, record_id=999)

        self.assertEqual(caught.exception.code, "record_not_found")


if __name__ == "__main__":
    unittest.main()
