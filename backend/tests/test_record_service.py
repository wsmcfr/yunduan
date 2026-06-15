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
from src.schemas.upload import FileObjectCreateRequest
from src.services.record_service import RecordService


class FakeCosClient:
    """记录检测记录删除期间请求清理的 COS 对象。"""

    def __init__(self) -> None:
        """初始化已删除对象列表。"""

        self.deleted_objects: list[tuple[str, str, str]] = []

    def delete_object(self, *, bucket_name: str, region: str, object_key: str) -> None:
        """记录一次对象删除请求，避免单测触发真实云端调用。"""

        self.deleted_objects.append((bucket_name, region, object_key))

    def build_object_access_url(self, *, bucket_name: str, region: str, object_key: str) -> str:
        """按 COS 公网访问格式生成测试预览地址。

        参数:
            bucket_name: 测试文件所属 bucket。
            region: 测试文件所属地域。
            object_key: 测试文件对象路径。

        返回:
            返回可预测的 URL 字符串，避免 AI 上下文测试依赖真实 COS 客户端。
        """

        return f"https://{bucket_name}.cos.{region}.myqcloud.com/{object_key}"


class FakeCloudDetectionService:
    """模拟云端检测服务，避免记录服务测试加载真实 ONNX 模型。"""

    def __init__(self) -> None:
        """初始化调用记录列表。"""

        self.calls: list[dict[str, object]] = []

    def run_for_record(self, *, record: DetectionRecord, trigger: str) -> dict:
        """返回固定云端检测上下文，并携带一张云端结果图元数据。

        参数:
            record: 记录服务传入的检测记录，测试会校验它能拿到当前文件列表。
            trigger: 触发来源，自动上传或手动重跑。

        返回:
            返回可直接写入 DetectionRecord.cloud_detection_context 的字典。
        """

        self.calls.append({"record_id": record.id, "trigger": trigger, "file_count": len(record.files)})
        return {
            "status": "success",
            "trigger": trigger,
            "source_file": {
                "file_id": record.files[0].id if record.files else None,
                "file_kind": record.files[0].file_kind.value if record.files else None,
                "object_key": record.files[0].object_key if record.files else None,
            },
            "classification": {"predicted_result": "bad", "predicted_label": "washer_bad"},
            "segmentation": {"predicted_result": "bad", "defect_pixels": 1432},
            "comparison": {
                "mp157_result": record.result.value,
                "cloud_result": "bad",
                "is_conflict": record.result != DetectionResult.BAD,
                "suggested_action": "建议人工复核，并考虑修正板端结果。",
            },
            "generated_files": [
                {
                    "artifact_type": "cloud_unet_overlay",
                    "display_name": "云端 UNet 缺陷叠加图",
                    "file_kind": "annotated",
                    "storage_provider": "cos",
                    "bucket_name": "demo-bucket",
                    "region": "ap-shanghai",
                    "object_key": f"detections/{record.record_no}/cloud_detection/overlay.jpg",
                    "content_type": "image/jpeg",
                    "size_bytes": 4096,
                    "etag": "overlay-etag",
                    "preview_url": f"https://demo-bucket.cos.ap-shanghai.myqcloud.com/detections/{record.record_no}/cloud_detection/overlay.jpg",
                }
            ],
            "summary_text": "云端模型检测完成：MobileNetV3-Small 与 UNet 均倾向不良。",
            "error_message": None,
        }


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

    def _create_record_file(
        self,
        *,
        record: DetectionRecord,
        object_key: str,
        file_kind: FileKind = FileKind.SOURCE,
        uploaded_at: datetime | None = None,
    ) -> FileObject:
        """创建检测记录文件对象。

        参数:
            record: 文件归属的检测记录。
            object_key: COS 对象路径，用于验证删除、AI 引用和模型产物识别。
            file_kind: 文件类型；默认源图，AI 上下文测试会传入标注图和缩略图。
            uploaded_at: 上传时间；不传时使用固定测试时间，保证排序断言稳定。

        返回:
            返回已持久化的 FileObject，方便测试继续读取 id 和对象路径。
        """

        file_object = FileObject(
            company_id=self.company.id,
            detection_record_id=record.id,
            file_kind=file_kind,
            storage_provider=StorageProvider.COS,
            bucket_name="demo-bucket",
            region="ap-shanghai",
            object_key=object_key,
            content_type="image/jpeg",
            size_bytes=2048,
            etag=None,
            uploaded_at=uploaded_at or datetime(2026, 5, 8, 9, 1, 0, tzinfo=timezone.utc),
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
            part_category="垫圈类",
            auto_create_part=True,
        )

        record = self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertNotEqual(record.part_id, self.part.id)
        self.assertEqual(record.part.part_code, "wave_washer")
        self.assertEqual(record.part.name, "波形垫圈")
        self.assertEqual(record.part.category, "垫圈类")
        self.assertEqual(record.device_context["part_code"], "wave_washer")

    def test_create_record_auto_creates_gasket_as_wave_washer(self) -> None:
        """历史模型标签 gasket 代表波形垫圈，云端自动创建时不能显示成垫片。"""

        payload = self._build_record_payload(
            record_no="REC-AUTO-GASKET-0001",
            part_code="gasket",
            auto_create_part=True,
        )

        record = self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertEqual(record.part.part_code, "gasket")
        self.assertEqual(record.part.name, "波形垫圈")
        self.assertEqual(record.part.category, "垫圈类")

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

    def test_create_record_normalizes_legacy_part_when_using_part_id(self) -> None:
        """旧客户端只传 part_id 时，也应修正历史 gasket 显示名和大类。"""

        self.part.part_code = "gasket"
        self.part.name = "垫片"
        self.part.category = "垫圈"
        self.db.commit()

        payload = self._build_record_payload(
            record_no="REC-LEGACY-PART-ID-0001",
            part_id=self.part.id,
        )

        record = self.service.create_record(company_id=self.company.id, payload=payload)

        self.assertEqual(record.part_id, self.part.id)
        self.assertEqual(record.part.part_code, "gasket")
        self.assertEqual(record.part.name, "波形垫圈")
        self.assertEqual(record.part.category, "垫圈类")

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

    def test_ai_context_references_four_model_artifact_images_with_purpose(self) -> None:
        """AI 对话上下文应带齐四张模型产物图，并说明每张图的质检用途。"""

        record = self._create_detection_record(record_no="REC-AI-FILES-0001")
        base_time = datetime(2026, 5, 20, 7, 48, 55, tzinfo=timezone.utc)
        self._create_record_file(
            record=record,
            file_kind=FileKind.ANNOTATED,
            object_key="detections/REC-AI-FILES-0001/annotated/001_segment_20260520_154855_62_mask.png",
            uploaded_at=base_time,
        )
        self._create_record_file(
            record=record,
            file_kind=FileKind.ANNOTATED,
            object_key="detections/REC-AI-FILES-0001/annotated/002_segment_20260520_154855_62_overlay.jpg",
            uploaded_at=base_time,
        )
        self._create_record_file(
            record=record,
            file_kind=FileKind.ANNOTATED,
            object_key="detections/REC-AI-FILES-0001/annotated/003_mobilenetv3_classification_gasket_good.jpg",
            uploaded_at=base_time,
        )
        self._create_record_file(
            record=record,
            file_kind=FileKind.SOURCE,
            object_key="detections/REC-AI-FILES-0001/source/004_segment_20260520_154855_62_raw.jpg",
            uploaded_at=base_time,
        )
        self._create_record_file(
            record=record,
            file_kind=FileKind.THUMBNAIL,
            object_key="detections/REC-AI-FILES-0001/thumbnail/005_thumb.jpg",
            uploaded_at=base_time,
        )
        self.db.refresh(record)

        referenced_files = self.service._build_ai_referenced_files(record=record)  # type: ignore[attr-defined]

        self.assertEqual(len(referenced_files), 4)
        self.assertEqual(
            [item["object_key"].split("/")[-1] for item in referenced_files],
            [
                "001_segment_20260520_154855_62_mask.png",
                "002_segment_20260520_154855_62_overlay.jpg",
                "003_mobilenetv3_classification_gasket_good.jpg",
                "004_segment_20260520_154855_62_raw.jpg",
            ],
        )
        self.assertIn("UNet 分割 mask", referenced_files[0]["analysis_purpose"])
        self.assertIn("UNet 分割叠加图", referenced_files[1]["analysis_purpose"])
        self.assertIn("MobileNetV3-Small 分类", referenced_files[2]["analysis_purpose"])
        self.assertIn("原始采集图", referenced_files[3]["analysis_purpose"])

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

    def test_create_file_object_runs_cloud_detection_after_source_upload(self) -> None:
        """登记 source 图片后，应自动运行云端检测并保存上下文和云端结果图元数据。"""

        record = self._create_detection_record(record_no="REC-CLOUD-AUTO-0001")
        fake_cloud_detection_service = FakeCloudDetectionService()
        service = RecordService(
            self.db,
            cos_client=self.cos_client,
            cloud_detection_service=fake_cloud_detection_service,
        )

        file_object = service.create_file_object(
            company_id=self.company.id,
            record_id=record.id,
            payload=FileObjectCreateRequest(
                file_kind=FileKind.SOURCE,
                storage_provider=StorageProvider.COS,
                bucket_name="demo-bucket",
                region="ap-shanghai",
                object_key="detections/REC-CLOUD-AUTO-0001/source/raw.jpg",
                content_type="image/jpeg",
                size_bytes=2048,
                uploaded_at=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
            ),
        )

        self.db.refresh(record)
        generated_file = self.db.scalar(
            select(FileObject).where(
                FileObject.detection_record_id == record.id,
                FileObject.object_key == "detections/REC-CLOUD-AUTO-0001/cloud_detection/overlay.jpg",
            )
        )
        self.assertEqual(file_object.file_kind, FileKind.SOURCE)
        self.assertEqual(fake_cloud_detection_service.calls[0]["trigger"], "auto_after_upload")
        self.assertEqual(fake_cloud_detection_service.calls[0]["file_count"], 1)
        self.assertEqual(record.cloud_detection_context["status"], "success")
        self.assertEqual(record.cloud_detection_context["trigger"], "auto_after_upload")
        self.assertIsNotNone(generated_file)
        self.assertEqual(generated_file.file_kind, FileKind.ANNOTATED)
        self.assertEqual(generated_file.content_type, "image/jpeg")

    def test_create_file_object_skips_cloud_detection_for_thumbnail(self) -> None:
        """缩略图登记不应触发云端模型检测，避免重复跑模型。"""

        record = self._create_detection_record(record_no="REC-CLOUD-THUMB-0001")
        fake_cloud_detection_service = FakeCloudDetectionService()
        service = RecordService(
            self.db,
            cos_client=self.cos_client,
            cloud_detection_service=fake_cloud_detection_service,
        )

        service.create_file_object(
            company_id=self.company.id,
            record_id=record.id,
            payload=FileObjectCreateRequest(
                file_kind=FileKind.THUMBNAIL,
                storage_provider=StorageProvider.COS,
                bucket_name="demo-bucket",
                region="ap-shanghai",
                object_key="detections/REC-CLOUD-THUMB-0001/thumbnail/thumb.jpg",
                content_type="image/jpeg",
                size_bytes=512,
            ),
        )

        self.db.refresh(record)
        self.assertEqual(fake_cloud_detection_service.calls, [])
        self.assertIsNone(record.cloud_detection_context)

    def test_run_cloud_detection_updates_record_context_and_generated_files(self) -> None:
        """手动重新检测应更新记录上下文，并把云端结果图登记为文件对象。"""

        record = self._create_detection_record(record_no="REC-CLOUD-MANUAL-0001")
        self._create_record_file(
            record=record,
            file_kind=FileKind.SOURCE,
            object_key="detections/REC-CLOUD-MANUAL-0001/source/raw.jpg",
        )
        fake_cloud_detection_service = FakeCloudDetectionService()
        service = RecordService(
            self.db,
            cos_client=self.cos_client,
            cloud_detection_service=fake_cloud_detection_service,
        )

        updated_record = service.run_cloud_detection(
            company_id=self.company.id,
            record_id=record.id,
            trigger="manual_rerun",
        )

        generated_file = self.db.scalar(
            select(FileObject).where(
                FileObject.detection_record_id == record.id,
                FileObject.object_key == "detections/REC-CLOUD-MANUAL-0001/cloud_detection/overlay.jpg",
            )
        )
        self.assertEqual(updated_record.cloud_detection_context["trigger"], "manual_rerun")
        self.assertEqual(fake_cloud_detection_service.calls[0]["trigger"], "manual_rerun")
        self.assertIsNotNone(generated_file)
        self.assertTrue(any(item.object_key.endswith("overlay.jpg") for item in updated_record.files))


if __name__ == "__main__":
    unittest.main()
