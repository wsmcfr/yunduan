"""云端本地模型检测服务测试。"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, FileKind, ReviewStatus, StorageProvider
from src.db.models.file_object import FileObject
from src.services.cloud_detection_service import (
    ClassificationPrediction,
    CloudDetectionService,
    SegmentationPrediction,
)


@dataclass
class FakeCloudDetectionSettings:
    """云端检测服务测试配置，只保留服务会读取的字段。"""

    cloud_detection_enabled: bool = True
    cloud_detection_classifier_model_path: str = "D:\\model_picture\\checkpoints_classify\\defect_classifier.onnx"
    cloud_detection_segment_model_path: str = "D:\\model_picture\\checkpoints_unet_test\\defect_unet_test.onnx"
    cloud_detection_defect_pixel_threshold: int = 80
    cloud_detection_max_image_bytes: int = 8 * 1024 * 1024
    cos_bucket: str = "cloud-bucket"
    cos_region: str = "ap-shanghai"


class FakeCosClient:
    """记录云端检测服务读取和上传的 COS 对象。"""

    def __init__(self, *, image_bytes: bytes = b"fake-image") -> None:
        """初始化假 COS 客户端。

        参数:
            image_bytes: read_file_bytes 返回给服务的图片字节；测试中不会真的解码。
        """

        self.image_bytes = image_bytes
        self.read_requests: list[dict[str, Any]] = []
        self.upload_requests: list[dict[str, Any]] = []

    def read_file_bytes(
        self,
        *,
        bucket_name: str,
        region: str,
        object_key: str,
        timeout_seconds: int = 60,
        max_bytes: int | None = None,
    ) -> dict[str, str | bytes]:
        """记录下载请求并返回固定图片字节。"""

        self.read_requests.append(
            {
                "bucket_name": bucket_name,
                "region": region,
                "object_key": object_key,
                "timeout_seconds": timeout_seconds,
                "max_bytes": max_bytes,
            }
        )
        return {"access_url": "https://cos.example/source.jpg", "content_type": "image/jpeg", "data": self.image_bytes}

    def upload_file_bytes(
        self,
        *,
        bucket_name: str,
        region: str,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        """记录上传请求，模拟 COS 写入云端检测结果图。"""

        self.upload_requests.append(
            {
                "bucket_name": bucket_name,
                "region": region,
                "object_key": object_key,
                "data": data,
                "content_type": content_type,
            }
        )
        return {
            "bucket_name": bucket_name,
            "region": region,
            "object_key": object_key,
            "content_type": content_type,
            "size_bytes": len(data),
            "etag": "fake-etag",
        }

    def build_object_access_url(self, *, bucket_name: str, region: str, object_key: str) -> str:
        """返回可预测的预览地址，供 context.generated_files 使用。"""

        return f"https://{bucket_name}.cos.{region}.myqcloud.com/{object_key}"


class FakeClassifier:
    """返回固定 MobileNetV3-Small 分类结果。"""

    def __init__(self, *, label: str = "washer_bad", probabilities: dict[str, float] | None = None) -> None:
        """初始化分类假模型。

        参数:
            label: 模拟模型预测的类别标签。
            probabilities: 模拟 softmax 概率分布。
        """

        self.label = label
        self.probabilities = probabilities or {"washer_bad": 0.97, "washer_good": 0.03}

    def predict(self, image_bgr: object) -> ClassificationPrediction:
        """返回固定分类预测对象。"""

        return ClassificationPrediction(
            model_name="MobileNetV3-Small",
            model_path="classifier.onnx",
            predicted_label=self.label,
            confidence=max(self.probabilities.values()),
            probabilities=self.probabilities,
            inference_ms=11.5,
            visualization_bytes=b"classification-jpeg",
            visualization_content_type="image/jpeg",
        )


class FakeSegmenter:
    """返回固定 UNet 分割结果。"""

    def __init__(self, *, defect_pixels: int = 1432, class_pixel_counts: dict[str, int] | None = None) -> None:
        """初始化分割假模型。

        参数:
            defect_pixels: 模拟非背景缺陷像素数量。
            class_pixel_counts: 模拟各缺陷类别像素计数。
        """

        self.defect_pixels = defect_pixels
        self.class_pixel_counts = class_pixel_counts or {"scratch": defect_pixels}

    def predict(self, image_bgr: object) -> SegmentationPrediction:
        """返回固定分割预测对象。"""

        return SegmentationPrediction(
            model_name="UNet-MobileNetV3",
            model_path="segmenter.onnx",
            defect_pixels=self.defect_pixels,
            class_pixel_counts=self.class_pixel_counts,
            inference_ms=22.5,
            overlay_bytes=b"overlay-jpeg",
            overlay_content_type="image/jpeg",
            mask_bytes=b"mask-png",
            mask_content_type="image/png",
        )


class CloudDetectionServiceTestCase(unittest.TestCase):
    """验证云端检测服务的上下文生成、COS 上传和错误路径。"""

    def _make_file(
        self,
        *,
        file_id: int,
        file_kind: FileKind,
        object_key: str,
        uploaded_at: datetime,
    ) -> FileObject:
        """构造不入库的文件对象，模拟详情记录里已有的 source/annotated 图片。"""

        return FileObject(
            id=file_id,
            company_id=1,
            detection_record_id=1,
            file_kind=file_kind,
            storage_provider=StorageProvider.COS,
            bucket_name="demo-bucket",
            region="ap-shanghai",
            object_key=object_key,
            content_type="image/jpeg",
            size_bytes=2048,
            etag=None,
            uploaded_at=uploaded_at,
            storage_last_modified=None,
        )

    def _make_record(self, *, result: DetectionResult = DetectionResult.GOOD) -> DetectionRecord:
        """构造不入库的检测记录，供云端检测服务读取文件和 MP157 初检结果。"""

        record = DetectionRecord(
            id=1,
            company_id=1,
            record_no="REC-CLOUD-0001",
            part_id=1,
            device_id=1,
            result=result,
            review_status=ReviewStatus.PENDING,
            captured_at=datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
        )
        record.files = [
            self._make_file(
                file_id=11,
                file_kind=FileKind.ANNOTATED,
                object_key="detections/REC-CLOUD-0001/annotated/board_overlay.jpg",
                uploaded_at=datetime(2026, 6, 15, 9, 1, 0, tzinfo=timezone.utc),
            ),
            self._make_file(
                file_id=12,
                file_kind=FileKind.SOURCE,
                object_key="detections/REC-CLOUD-0001/source/raw.jpg",
                uploaded_at=datetime(2026, 6, 15, 9, 2, 0, tzinfo=timezone.utc),
            ),
        ]
        return record

    def _make_service(self, *, cos_client: FakeCosClient | None = None) -> CloudDetectionService:
        """创建注入假模型和假 COS 的云端检测服务。"""

        return CloudDetectionService(
            cos_client=cos_client or FakeCosClient(),
            classifier=FakeClassifier(),
            segmenter=FakeSegmenter(),
            settings=FakeCloudDetectionSettings(),
            image_decoder=lambda _data: object(),
        )

    def test_run_cloud_detection_prefers_source_file_and_builds_summary(self) -> None:
        """同时存在 source 和 annotated 时，云端检测必须优先复核板端原图。"""

        cos_client = FakeCosClient()
        service = self._make_service(cos_client=cos_client)

        context = service.run_for_record(record=self._make_record(), trigger="manual_rerun")

        self.assertEqual(context["status"], "success")
        self.assertEqual(context["trigger"], "manual_rerun")
        self.assertEqual(context["source_file"]["file_kind"], "source")
        self.assertEqual(cos_client.read_requests[0]["object_key"], "detections/REC-CLOUD-0001/source/raw.jpg")
        self.assertEqual(context["classification"]["predicted_result"], "bad")
        self.assertEqual(context["segmentation"]["predicted_result"], "bad")
        self.assertIn("坏件概率", context["summary_text"])
        self.assertIn("UNet", context["summary_text"])

    def test_run_cloud_detection_marks_conflict_when_mp157_result_differs(self) -> None:
        """云端结论与 MP157 初检不同，应在 comparison 中明确标记冲突。"""

        context = self._make_service().run_for_record(record=self._make_record(result=DetectionResult.GOOD), trigger="manual_rerun")

        self.assertTrue(context["comparison"]["is_conflict"])
        self.assertEqual(context["comparison"]["mp157_result"], "good")
        self.assertEqual(context["comparison"]["cloud_result"], "bad")
        self.assertIn("人工复核", context["comparison"]["suggested_action"])

    def test_run_cloud_detection_uploads_generated_images_to_cos_context(self) -> None:
        """云端检测生成的 mask、叠加图和分类结果图要上传 COS 并写入 context。"""

        cos_client = FakeCosClient()
        context = self._make_service(cos_client=cos_client).run_for_record(
            record=self._make_record(),
            trigger="auto_after_upload",
        )

        uploaded_artifacts = [item["artifact_type"] for item in context["generated_files"]]
        self.assertEqual(
            uploaded_artifacts,
            ["cloud_unet_overlay", "cloud_unet_mask", "cloud_mobilenetv3_classification"],
        )
        self.assertEqual(len(cos_client.upload_requests), 3)
        self.assertTrue(all(request["object_key"].startswith("detections/REC-CLOUD-0001/cloud_detection/") for request in cos_client.upload_requests))
        self.assertTrue(all(item["preview_url"].startswith("https://cloud-bucket.cos.ap-shanghai.myqcloud.com/") for item in context["generated_files"]))
        self.assertIn("云端 UNet 缺陷叠加图", context["generated_files"][0]["display_name"])

    def test_run_cloud_detection_without_image_returns_failed_context(self) -> None:
        """记录没有 source 或 annotated 图片时，不抛异常，而是返回可展示的失败上下文。"""

        record = self._make_record()
        record.files = []

        context = self._make_service().run_for_record(record=record, trigger="manual_rerun")

        self.assertEqual(context["status"], "failed")
        self.assertIsNone(context["source_file"])
        self.assertIn("没有可用于检测", context["summary_text"])
        self.assertIn("没有可用于检测", context["error_message"])


if __name__ == "__main__":
    unittest.main()
