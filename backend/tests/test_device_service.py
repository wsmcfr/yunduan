"""设备服务删除行为回归测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.core.errors import NotFoundError
from src.core.errors import BadRequestError
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
from src.services.device_service import DeviceService
from src.schemas.device import DeviceCreateRequest, DeviceUpdateRequest


class FakeCosClient:
    """记录设备彻底删除期间请求清理的 COS 对象。"""

    def __init__(self) -> None:
        """初始化已删除对象列表。"""

        self.deleted_objects: list[tuple[str, str, str]] = []

    def delete_object(self, *, bucket_name: str, region: str, object_key: str) -> None:
        """记录一次对象删除请求，避免单测触发真实云端调用。"""

        self.deleted_objects.append((bucket_name, region, object_key))


class DeviceServiceTestCase(unittest.TestCase):
    """验证设备服务在删除设备时保留检测追溯链路。"""

    def setUp(self) -> None:
        """为每个测试准备只包含设备删除所需表结构的内存数据库。"""

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
        self.service = DeviceService(self.db, cos_client=self.cos_client)
        self.company = self._create_company()

    def tearDown(self) -> None:
        """释放测试数据库连接，避免测试之间互相污染。"""

        self.db.close()
        self.engine.dispose()

    def _create_company(self) -> Company:
        """创建标准测试公司，设备和检测记录都必须归属到它。"""

        company = Company(
            name="设备删除测试公司",
            contact_name="测试联系人",
            note="用于设备删除服务测试。",
            invite_code="DEVICEDEL",
            is_active=True,
            is_system_reserved=False,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def _create_device(self, *, code: str = "MP157-DELETE-01") -> Device:
        """创建一台 MP157 设备，模拟云端当前唯一需要建档的主控节点。"""

        device = Device(
            company_id=self.company.id,
            device_code=code,
            name="MP157 主控设备",
            device_type=DeviceType.MP157,
            status=DeviceStatus.ONLINE,
            firmware_version="sim-1.0.0",
            ip_address="192.168.10.157",
            last_seen_at=datetime(2026, 5, 6, 14, 0, 0, tzinfo=timezone.utc),
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def _create_part(self) -> Part:
        """创建检测记录依赖的零件定义。"""

        part = Part(
            company_id=self.company.id,
            part_code="PART-DELETE-01",
            name="删除保护测试零件",
            category="测试",
            description=None,
            is_active=True,
        )
        self.db.add(part)
        self.db.commit()
        self.db.refresh(part)
        return part

    def _create_detection_record(self, *, device: Device, part: Part) -> DetectionRecord:
        """创建引用指定设备的检测记录，用于验证删除保护。"""

        record = DetectionRecord(
            company_id=self.company.id,
            record_no="REC-DEVICE-DELETE-0001",
            part_id=part.id,
            device_id=device.id,
            result=DetectionResult.GOOD,
            review_status=ReviewStatus.PENDING,
            surface_result=DetectionResult.GOOD,
            backlight_result=None,
            eddy_result=None,
            defect_type=None,
            defect_desc=None,
            confidence_score=0.98,
            vision_context={"source": "mp157"},
            sensor_context={"f4_serial": {"eddy_mv": 120}},
            decision_context=None,
            device_context={"mp157": {"ip": "192.168.10.157"}},
            captured_at=datetime(2026, 5, 6, 14, 1, 0, tzinfo=timezone.utc),
            detected_at=None,
            uploaded_at=None,
            storage_last_modified=None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _create_record_file(self, *, record: DetectionRecord) -> FileObject:
        """创建检测记录文件对象，验证彻底删除会清理图片元数据。"""

        file_object = FileObject(
            company_id=self.company.id,
            detection_record_id=record.id,
            file_kind=FileKind.SOURCE,
            storage_provider=StorageProvider.COS,
            bucket_name="demo-bucket",
            region="ap-shanghai",
            object_key="detections/demo/source.jpg",
            content_type="image/jpeg",
            size_bytes=1024,
            etag=None,
            uploaded_at=datetime(2026, 5, 6, 14, 2, 0, tzinfo=timezone.utc),
            storage_last_modified=None,
        )
        self.db.add(file_object)
        self.db.commit()
        self.db.refresh(file_object)
        return file_object

    def _create_record_review(self, *, record: DetectionRecord) -> ReviewRecord:
        """创建检测记录审核记录，验证彻底删除会清理复核历史。"""

        review = ReviewRecord(
            company_id=self.company.id,
            detection_record_id=record.id,
            reviewer_id=None,
            review_source=ReviewSource.MANUAL,
            decision=DetectionResult.GOOD,
            defect_type=None,
            comment="确认良品",
            reviewed_at=datetime(2026, 5, 6, 14, 3, 0, tzinfo=timezone.utc),
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def test_delete_device_removes_unreferenced_device(self) -> None:
        """没有检测记录引用时，管理员可以删除设备档案。"""

        device = self._create_device()

        deleted_record_count = self.service.delete_device(company_id=self.company.id, device_id=device.id)

        persisted_device = self.db.scalar(select(Device).where(Device.id == device.id))
        self.assertIsNone(persisted_device)
        self.assertEqual(deleted_record_count, 0)

    def test_delete_device_purges_detection_records_when_device_is_deleted(self) -> None:
        """已有检测记录引用时，确认删除会一并清理检测历史。"""

        device = self._create_device()
        part = self._create_part()
        record = self._create_detection_record(device=device, part=part)
        file_object = self._create_record_file(record=record)
        review = self._create_record_review(record=record)
        record_id = record.id
        file_object_id = file_object.id
        review_id = review.id

        deleted_record_count = self.service.delete_device(company_id=self.company.id, device_id=device.id)

        persisted_device = self.db.scalar(select(Device).where(Device.id == device.id))
        persisted_record = self.db.scalar(select(DetectionRecord).where(DetectionRecord.id == record_id))
        persisted_file = self.db.scalar(select(FileObject).where(FileObject.id == file_object_id))
        persisted_review = self.db.scalar(select(ReviewRecord).where(ReviewRecord.id == review_id))
        self.assertIsNone(persisted_device)
        self.assertIsNone(persisted_record)
        self.assertIsNone(persisted_file)
        self.assertIsNone(persisted_review)
        self.assertEqual(deleted_record_count, 1)
        self.assertEqual(
            self.cos_client.deleted_objects,
            [("demo-bucket", "ap-shanghai", "detections/demo/source.jpg")],
        )

    def test_list_devices_attaches_record_and_image_counts(self) -> None:
        """设备列表应带上检测记录和图片数量，便于前端删除前二次确认。"""

        device = self._create_device()
        part = self._create_part()
        record = self._create_detection_record(device=device, part=part)
        self._create_record_file(record=record)

        _, devices = self.service.list_devices(
            company_id=self.company.id,
            keyword=None,
            status=None,
            skip=0,
            limit=10,
        )

        self.assertEqual(len(devices), 1)
        self.assertEqual(getattr(devices[0], "record_count"), 1)
        self.assertEqual(getattr(devices[0], "image_count"), 1)

    def test_create_device_rejects_non_mp157_type(self) -> None:
        """云端设备档案只允许创建 MP157 主控设备。"""

        payload = DeviceCreateRequest(
            device_code="F4-SHOULD-BE-SERIAL-01",
            name="不应单独建档的 F4",
            device_type=DeviceType.F4,
            status=DeviceStatus.ONLINE,
            firmware_version=None,
            ip_address=None,
            last_seen_at=None,
        )

        with self.assertRaises(BadRequestError) as caught:
            self.service.create_device(company_id=self.company.id, payload=payload)

        self.assertEqual(caught.exception.code, "device_type_must_be_mp157")

    def test_update_device_rejects_non_mp157_type(self) -> None:
        """编辑设备时也不能把 MP157 主控改成 F4、网关或其他类型。"""

        device = self._create_device()
        payload = DeviceUpdateRequest(device_type=DeviceType.F4)

        with self.assertRaises(BadRequestError) as caught:
            self.service.update_device(company_id=self.company.id, device_id=device.id, payload=payload)

        self.assertEqual(caught.exception.code, "device_type_must_be_mp157")

    def test_device_model_defaults_to_mp157(self) -> None:
        """绕过请求 Schema 创建设备对象时，ORM 默认类型也应保持 MP157。"""

        device = Device(
            company_id=self.company.id,
            device_code="MP157-DEFAULT-01",
            name="默认类型测试主控",
            status=DeviceStatus.OFFLINE,
            firmware_version=None,
            ip_address=None,
            last_seen_at=None,
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)

        self.assertEqual(device.device_type, DeviceType.MP157)

    def test_delete_device_rejects_missing_device(self) -> None:
        """删除不存在或不属于当前公司的设备时，应返回不存在错误。"""

        with self.assertRaises(NotFoundError) as caught:
            self.service.delete_device(company_id=self.company.id, device_id=999)

        self.assertEqual(caught.exception.code, "device_not_found")
