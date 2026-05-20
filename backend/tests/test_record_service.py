"""检测记录服务删除行为回归测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.core.errors import BadRequestError, NotFoundError
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
from src.schemas.detection_record import DetectionRecordCreateRequest
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

    def _build_record_payload(
        self,
        *,
        record_no: str,
        part_id: int | None = None,
        part_code: str | None = None,
        part_name: str | None = None,
        part_category: str | None = None,
        auto_create_part: bool = False,
    ) -> DetectionRecordCreateRequest:
        """构造检测记录创建请求，便于测试 part_id 与 part_code 两条入口。

        参数:
            record_no: 本次检测记录编号，测试中显式传入以避免随机编号影响断言。
            part_id: 已有零件主键；传入时沿用旧的创建记录路径。
            part_code: MP157 上报的零件编码；未传 part_id 时服务层按它查找或自动创建零件。
            part_name: 自动创建零件时使用的中文名称。
            part_category: 自动创建零件时使用的分类。
            auto_create_part: 是否允许服务层在 part_code 不存在时创建零件。

        返回:
            返回 DetectionRecordCreateRequest，供 RecordService.create_record() 直接使用。
        """

        return DetectionRecordCreateRequest(
            record_no=record_no,
            part_id=part_id,
            part_code=part_code,
            part_name=part_name,
            part_category=part_category,
            auto_create_part=auto_create_part,
            device_id=self.device.id,
            result=DetectionResult.GOOD,
            review_status=ReviewStatus.PENDING,
            surface_result=DetectionResult.GOOD,
            backlight_result=None,
            eddy_result=None,
            defect_type=None,
            defect_desc=None,
            confidence_score=0.91,
            vision_context={"model": "mobilenetv3-small"},
            sensor_context=None,
            decision_context=None,
            device_context={
                "part_code": part_code,
                "class_label": f"{part_code}_good" if part_code else None,
            },
            captured_at=datetime(2026, 5, 20, 3, 39, 59, tzinfo=timezone.utc),
            detected_at=None,
            uploaded_at=None,
            storage_last_modified=None,
        )

    def test_create_record_auto_creates_part_from_part_code(self) -> None:
        """MP157 只上传 part_code 且允许自动创建时，应先创建零件再创建检测记录。"""

        payload = self._build_record_payload(
            record_no="REC-AUTO-PART-0001",
            part_code="wave_washer",
            part_name="波形垫圈",
            part_category="弹性垫圈",
            auto_create_part=True,
        )

        record = self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertNotEqual(record.part_id, self.part.id)
        self.assertEqual(record.part.part_code, "wave_washer")
        self.assertEqual(record.part.name, "波形垫圈")
        self.assertEqual(record.part.category, "弹性垫圈")
        self.assertEqual(record.device_context["part_code"], "wave_washer")

    def test_create_record_reuses_existing_part_code_without_auto_create(self) -> None:
        """MP157 上传的 part_code 已存在时，即使未开启自动创建，也应复用已有零件。"""

        payload = self._build_record_payload(
            record_no="REC-REUSE-PART-0001",
            part_code=self.part.part_code,
            auto_create_part=False,
        )

        record = self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertEqual(record.part_id, self.part.id)
        self.assertEqual(record.part.part_code, self.part.part_code)

    def test_create_record_rejects_unknown_part_code_without_auto_create(self) -> None:
        """MP157 上传未知 part_code 但未允许自动创建时，应拒绝创建记录避免误建主数据。"""

        payload = self._build_record_payload(
            record_no="REC-UNKNOWN-PART-0001",
            part_code="unknown_wave_washer",
            auto_create_part=False,
        )

        with self.assertRaises(NotFoundError) as caught:
            self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertEqual(caught.exception.code, "part_not_found")

    def test_create_record_requires_part_id_or_part_code(self) -> None:
        """创建检测记录必须至少提供 part_id 或 part_code 之一。"""

        payload = self._build_record_payload(
            record_no="REC-MISSING-PART-0001",
        )

        with self.assertRaises(BadRequestError) as caught:
            self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertEqual(caught.exception.code, "part_identity_required")

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
