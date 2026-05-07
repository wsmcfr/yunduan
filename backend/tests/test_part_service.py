"""零件服务清理行为回归测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.db.models.company import Company
from src.db.models.detection_record import DetectionRecord
from src.db.models.device import Device
from src.db.models.enums import DetectionResult, DeviceStatus, DeviceType, ReviewStatus
from src.db.models.file_object import FileObject
from src.db.models.part import Part
from src.db.models.review_record import ReviewRecord
from src.services.part_service import PartService


class PartServiceTestCase(unittest.TestCase):
    """验证零件服务在列表查询前清理历史模拟残留。"""

    def setUp(self) -> None:
        """为每个测试准备只包含零件列表所需表结构的内存数据库。"""

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
        self.service = PartService(self.db)
        self.company = self._create_company()
        self.device = self._create_device()

    def tearDown(self) -> None:
        """释放测试数据库连接，避免测试之间互相污染。"""

        self.db.close()
        self.engine.dispose()

    def _create_company(self) -> Company:
        """创建标准测试公司，零件和检测记录都必须归属到它。"""

        company = Company(
            name="零件清理测试公司",
            contact_name="测试联系人",
            note="用于零件服务清理测试。",
            invite_code="PARTCLEAN",
            is_active=True,
            is_system_reserved=False,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def _create_device(self) -> Device:
        """创建一台 MP157 设备，供仍被引用的零件生成检测记录。"""

        device = Device(
            company_id=self.company.id,
            device_code="MP157-PART-CLEAN-01",
            name="零件清理测试主控",
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

    def _create_part(self, *, code: str) -> Part:
        """创建零件类型测试数据。

        参数:
            code: 零件编码；`SIM-PART-` 前缀用于模拟历史导入残留。

        返回:
            已写入数据库并刷新后的零件对象。
        """

        part = Part(
            company_id=self.company.id,
            part_code=code,
            name=f"{code} 测试零件",
            category="测试",
            description=None,
            is_active=True,
        )
        self.db.add(part)
        self.db.commit()
        self.db.refresh(part)
        return part

    def _create_detection_record(self, *, part: Part, record_no: str) -> DetectionRecord:
        """创建引用指定零件的检测记录，让该零件不能被残留清理误删。"""

        record = DetectionRecord(
            company_id=self.company.id,
            record_no=record_no,
            part_id=part.id,
            device_id=self.device.id,
            result=DetectionResult.GOOD,
            review_status=ReviewStatus.PENDING,
            surface_result=DetectionResult.GOOD,
            backlight_result=None,
            eddy_result=None,
            defect_type=None,
            defect_desc=None,
            confidence_score=0.99,
            vision_context=None,
            sensor_context=None,
            decision_context=None,
            device_context=None,
            captured_at=datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc),
            detected_at=None,
            uploaded_at=None,
            storage_last_modified=None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def test_list_parts_cleans_unused_sim_parts_only(self) -> None:
        """列表查询前只清理无记录引用的 SIM 零件，不误删普通新建零件。"""

        unused_sim_part = self._create_part(code="SIM-PART-UNUSED")
        used_sim_part = self._create_part(code="SIM-PART-USED")
        manual_part = self._create_part(code="PART-MANUAL-NEW")
        unused_sim_part_id = unused_sim_part.id
        used_sim_part_id = used_sim_part.id
        manual_part_id = manual_part.id
        self._create_detection_record(part=used_sim_part, record_no="REC-PART-CLEAN-USED-SIM")

        total, items = self.service.list_parts(
            company_id=self.company.id,
            keyword=None,
            is_active=None,
            skip=0,
            limit=10,
        )

        removed_sim_part = self.db.scalar(select(Part).where(Part.id == unused_sim_part_id))
        persisted_used_sim_part = self.db.scalar(select(Part).where(Part.id == used_sim_part_id))
        persisted_manual_part = self.db.scalar(select(Part).where(Part.id == manual_part_id))
        self.assertIsNone(removed_sim_part)
        self.assertIsNotNone(persisted_used_sim_part)
        self.assertIsNotNone(persisted_manual_part)
        self.assertEqual(total, 2)
        self.assertEqual({item.part_code for item in items}, {"SIM-PART-USED", "PART-MANUAL-NEW"})


if __name__ == "__main__":
    unittest.main()
