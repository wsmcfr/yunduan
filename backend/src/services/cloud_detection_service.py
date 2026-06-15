"""云端本地 ONNX 模型检测服务。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.core.config import Settings, get_settings
from src.core.errors import AppError, IntegrationError
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import DetectionResult, FileKind, StorageProvider
from src.db.models.file_object import FileObject
from src.integrations.cos_client import CosClient

# ImageNet 归一化参数必须与 D:\model_picture 中训练和导出脚本保持一致。
# 两个模型都使用 RGB 通道顺序，OpenCV 解码后需要从 BGR 转成 RGB 再归一化。
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# 分类和分割模型当前都导出为 224x224 输入。
CLOUD_MODEL_INPUT_SIZE = 224

# 分类模型按“多种零件 + good/bad 后缀”命名；bad 总概率达到该阈值时优先拦截。
CLASSIFICATION_BAD_THRESHOLD = 0.5

# UNet 缺陷类别名称。索引 0 是背景，非背景像素用于缺陷面积判断。
SEGMENT_CLASS_NAMES = ["background", "scratch", "rust", "dent", "crack", "burr"]


@dataclass(frozen=True)
class ClassificationPrediction:
    """MobileNetV3-Small 分类模型输出。"""

    model_name: str
    model_path: str
    predicted_label: str
    confidence: float
    probabilities: dict[str, float]
    inference_ms: float
    visualization_bytes: bytes | None = None
    visualization_content_type: str | None = None


@dataclass(frozen=True)
class SegmentationPrediction:
    """UNet 分割模型输出。"""

    model_name: str
    model_path: str
    defect_pixels: int
    class_pixel_counts: dict[str, int]
    inference_ms: float
    overlay_bytes: bytes | None = None
    overlay_content_type: str | None = None
    mask_bytes: bytes | None = None
    mask_content_type: str | None = None


@dataclass(frozen=True)
class GeneratedImageArtifact:
    """云端模型生成的图片产物定义。"""

    artifact_type: str
    display_name: str
    file_kind: FileKind
    content_type: str
    data: bytes


def _utc_now() -> datetime:
    """返回带 UTC 时区的当前时间，便于测试和上下文序列化统一。"""

    return datetime.now(timezone.utc)


def _isoformat_utc(value: datetime) -> str:
    """将时间转换为 ISO 字符串。"""

    return value.isoformat()


def normalize_class_name(class_name: str) -> str:
    """规范化分类标签名称。

    参数:
        class_name: 模型标签，例如 ``washer_bad``、``Washer-Bad`` 或 ``washer good``。

    返回:
        返回小写、下划线分隔的标签名，方便后续按 token 判断 good/bad。
    """

    return str(class_name).strip().lower().replace("-", "_").replace(" ", "_")


def _class_tokens(class_name: str) -> list[str]:
    """把标签拆成 token，避免把 badge 这种单词误判为 bad。"""

    return [token for token in normalize_class_name(class_name).split("_") if token]


def is_bad_class_name(class_name: str) -> bool:
    """判断分类标签是否表示坏件。"""

    return "bad" in _class_tokens(class_name)


def is_good_class_name(class_name: str) -> bool:
    """判断分类标签是否表示良品。"""

    return "good" in _class_tokens(class_name)


def resolve_result_from_label(label: str) -> DetectionResult:
    """根据分类标签解析良坏结果。

    参数:
        label: 分类模型输出标签。

    返回:
        如果 token 中包含 ``bad`` 返回 BAD，包含 ``good`` 返回 GOOD，否则返回 UNCERTAIN。
    """

    if is_bad_class_name(label):
        return DetectionResult.BAD
    if is_good_class_name(label):
        return DetectionResult.GOOD
    return DetectionResult.UNCERTAIN


def _group_probability(probabilities: dict[str, float], *, group: str) -> float:
    """汇总 good 或 bad 标签组概率。"""

    matcher = is_bad_class_name if group == "bad" else is_good_class_name
    return float(sum(float(prob) for label, prob in probabilities.items() if matcher(label)))


def _safe_probability(value: float | None) -> float:
    """把概率限制在 0 到 1，避免异常模型输出污染展示文本。"""

    if value is None:
        return 0.0
    return min(max(float(value), 0.0), 1.0)


def _format_percent(value: float) -> str:
    """把 0~1 概率格式化为两位小数百分比。"""

    return f"{_safe_probability(value) * 100:.2f}%"


def decode_image_bytes(data: bytes) -> Any:
    """把图片字节解码为 OpenCV BGR 图像。

    参数:
        data: 从 COS 下载的图片字节。

    返回:
        OpenCV BGR 三通道图像。

    异常:
        图片无法解码时抛出 IntegrationError，调用方会转成可展示的失败上下文。
    """

    import cv2
    import numpy as np

    buffer = np.frombuffer(data, dtype=np.uint8)
    image_bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise IntegrationError(
            code="cloud_detection_image_decode_failed",
            message="云端检测无法解码板端上传的图片。",
        )
    return image_bgr


def _encode_image(image_bgr: Any, *, extension: str, content_type: str) -> tuple[bytes, str]:
    """把 OpenCV 图像编码为文件字节。

    参数:
        image_bgr: OpenCV BGR 图像。
        extension: 编码扩展名，例如 ``.jpg`` 或 ``.png``。
        content_type: 对应 MIME 类型。

    返回:
        返回图片字节和 MIME 类型。
    """

    import cv2

    params = [int(cv2.IMWRITE_JPEG_QUALITY), 95] if extension.lower() in {".jpg", ".jpeg"} else []
    ok, encoded = cv2.imencode(extension, image_bgr, params)
    if not ok:
        raise IntegrationError(
            code="cloud_detection_image_encode_failed",
            message="云端检测结果图编码失败。",
        )
    return encoded.tobytes(), content_type


class CloudClassifier:
    """MobileNetV3-Small 云端分类模型封装。"""

    def __init__(self, *, model_path: str, provider: str = "CPUExecutionProvider") -> None:
        """初始化分类模型封装。

        参数:
            model_path: ONNX 模型文件路径。
            provider: onnxruntime 执行后端，默认 CPU，避免云端没有 GPU 时失败。
        """

        self.model_path = model_path
        self.provider = provider
        self._session: Any | None = None
        self._class_names: list[str] | None = None

    def _get_session(self) -> Any:
        """懒加载 ONNX Runtime 会话。

        返回:
            返回可执行分类推理的 InferenceSession。

        说明:
            普通后端启动、列表查询和详情查询不应立即加载模型；只有真正触发云端检测时才创建会话。
        """

        if self._session is None:
            import onnxruntime as ort

            self._session = ort.InferenceSession(self.model_path, providers=[self.provider])
        return self._session

    def _resolve_labels_path(self) -> Path:
        """根据 ONNX 文件路径推导同名前缀的标签 JSON 路径。"""

        return Path(self.model_path).with_suffix("").with_name(Path(self.model_path).stem + "_labels.json")

    def _load_class_names(self) -> list[str]:
        """读取分类模型输出类别顺序。

        返回:
            按输出索引排序的类别名列表。

        说明:
            多零件分类不能猜测类别顺序，必须读取导出模型旁边的 ``*_labels.json``。
            如果是旧二分类模型且没有标签文件，才退回到 ``bad/good``。
        """

        if self._class_names is not None:
            return self._class_names

        session = self._get_session()
        output_shape = session.get_outputs()[0].shape
        output_num_classes = output_shape[-1] if output_shape and isinstance(output_shape[-1], int) else None
        labels_path = self._resolve_labels_path()
        if labels_path.exists():
            payload = json.loads(labels_path.read_text(encoding="utf-8"))
            if payload.get("idx_to_class"):
                idx_to_class = {int(idx): str(name) for idx, name in payload["idx_to_class"].items()}
                class_names = [idx_to_class[idx] for idx in sorted(idx_to_class)]
            elif payload.get("class_to_idx"):
                class_to_idx = {str(name): int(idx) for name, idx in payload["class_to_idx"].items()}
                class_names = [name for name, _idx in sorted(class_to_idx.items(), key=lambda item: item[1])]
            else:
                raise IntegrationError(
                    code="cloud_detection_labels_invalid",
                    message="分类模型标签文件格式不正确。",
                    details={"labels_path": str(labels_path)},
                )
        elif output_num_classes in {None, 2}:
            class_names = ["bad", "good"]
        else:
            raise IntegrationError(
                code="cloud_detection_labels_missing",
                message="分类模型缺少同名前缀的标签文件，无法确认多类别输出顺序。",
                details={"labels_path": str(labels_path), "num_classes": output_num_classes},
            )

        if output_num_classes is not None and len(class_names) != output_num_classes:
            raise IntegrationError(
                code="cloud_detection_labels_mismatch",
                message="分类模型标签数量与 ONNX 输出类别数不一致。",
                details={"labels_count": len(class_names), "num_classes": output_num_classes},
            )
        self._class_names = class_names
        return class_names

    def _preprocess(self, image_bgr: Any) -> tuple[Any, Any]:
        """执行分类模型预处理。

        参数:
            image_bgr: OpenCV BGR 图像。

        返回:
            返回 ONNX 输入 tensor 和 224x224 BGR 预览图。

        处理流程:
            1. Resize 到 224x224。
            2. BGR 转 RGB。
            3. 映射到 0~1，并按 ImageNet mean/std 标准化。
            4. HWC 转 NCHW，补 batch 维。
        """

        import cv2
        import numpy as np

        resized = cv2.resize(image_bgr, (CLOUD_MODEL_INPUT_SIZE, CLOUD_MODEL_INPUT_SIZE))
        image_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        image_float = image_rgb.astype(np.float32) / 255.0
        mean = np.array(IMAGENET_MEAN, dtype=np.float32)
        std = np.array(IMAGENET_STD, dtype=np.float32)
        image_norm = (image_float - mean) / std
        image_chw = np.transpose(image_norm, (2, 0, 1))
        return np.expand_dims(image_chw, axis=0).astype(np.float32), resized

    def _softmax(self, logits: Any) -> Any:
        """将模型 logits 转成 softmax 概率。"""

        import numpy as np

        stable_logits = logits - np.max(logits)
        exp_logits = np.exp(stable_logits)
        return exp_logits / np.sum(exp_logits)

    def _select_prediction(self, *, probabilities: dict[str, float], class_names: list[str]) -> tuple[str, float]:
        """按坏件总概率阈值选择最终分类标签。"""

        bad_total = _group_probability(probabilities, group="bad")
        if bad_total >= CLASSIFICATION_BAD_THRESHOLD:
            bad_labels = [label for label in class_names if is_bad_class_name(label)]
            if bad_labels:
                best_bad_label = max(bad_labels, key=lambda label: probabilities.get(label, 0.0))
                return best_bad_label, float(probabilities.get(best_bad_label, 0.0))

        best_label = max(class_names, key=lambda label: probabilities.get(label, 0.0))
        return best_label, float(probabilities.get(best_label, 0.0))

    def _draw_visualization(
        self,
        *,
        image_bgr: Any,
        predicted_label: str,
        confidence: float,
        good_probability: float,
        bad_probability: float,
        inference_ms: float,
    ) -> bytes:
        """生成分类结果可视化图片。

        参数:
            image_bgr: 224x224 BGR 图像。
            predicted_label: 最终预测标签。
            confidence: 预测标签概率。
            good_probability: good 标签组总概率。
            bad_probability: bad 标签组总概率。
            inference_ms: 推理耗时。

        返回:
            返回 JPEG 字节，用于上传 COS。
        """

        import cv2

        image = image_bgr.copy()
        result = resolve_result_from_label(predicted_label)
        color = (0, 0, 255) if result == DetectionResult.BAD else (0, 180, 0)
        cv2.rectangle(image, (0, 0), (image.shape[1], 28), color, -1)
        cv2.putText(
            image,
            f"{predicted_label}: {confidence * 100:.1f}%",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            f"GOOD {good_probability * 100:.1f}%  BAD {bad_probability * 100:.1f}%  {inference_ms:.1f}ms",
            (8, image.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        encoded_bytes, _content_type = _encode_image(image, extension=".jpg", content_type="image/jpeg")
        return encoded_bytes

    def predict(self, image_bgr: Any) -> ClassificationPrediction:
        """对图片执行分类推理。

        参数:
            image_bgr: OpenCV BGR 图像。

        返回:
            返回分类预测、概率分布和分类结果图字节。
        """

        session = self._get_session()
        class_names = self._load_class_names()
        input_tensor, resized = self._preprocess(image_bgr)
        input_name = session.get_inputs()[0].name

        started = time.perf_counter()
        outputs = session.run(None, {input_name: input_tensor})
        inference_ms = (time.perf_counter() - started) * 1000.0

        probs = self._softmax(outputs[0][0])
        probabilities = {label: float(probs[idx]) for idx, label in enumerate(class_names)}
        predicted_label, confidence = self._select_prediction(
            probabilities=probabilities,
            class_names=class_names,
        )
        good_probability = _group_probability(probabilities, group="good")
        bad_probability = _group_probability(probabilities, group="bad")
        visualization_bytes = self._draw_visualization(
            image_bgr=resized,
            predicted_label=predicted_label,
            confidence=confidence,
            good_probability=good_probability,
            bad_probability=bad_probability,
            inference_ms=inference_ms,
        )

        return ClassificationPrediction(
            model_name="MobileNetV3-Small",
            model_path=self.model_path,
            predicted_label=predicted_label,
            confidence=confidence,
            probabilities=probabilities,
            inference_ms=inference_ms,
            visualization_bytes=visualization_bytes,
            visualization_content_type="image/jpeg",
        )


class CloudSegmenter:
    """UNet-MobileNetV3 云端分割模型封装。"""

    def __init__(
        self,
        *,
        model_path: str,
        num_classes: int,
        provider: str = "CPUExecutionProvider",
        input_size: int = CLOUD_MODEL_INPUT_SIZE,
    ) -> None:
        """初始化分割模型封装。

        参数:
            model_path: UNet ONNX 模型路径。
            num_classes: 模型输出类别数，包含背景类。
            provider: onnxruntime 执行后端。
            input_size: 模型输入尺寸。
        """

        self.model_path = model_path
        self.num_classes = num_classes
        self.provider = provider
        self.input_size = input_size
        self._session: Any | None = None

    def _get_session(self) -> Any:
        """懒加载 UNet ONNX Runtime 会话。"""

        if self._session is None:
            import onnxruntime as ort

            self._session = ort.InferenceSession(self.model_path, providers=[self.provider])
        return self._session

    def _build_palette(self) -> Any:
        """生成 BGR 调色板，索引 0 背景固定为黑色。"""

        import cv2
        import numpy as np

        base_palette = np.array(
            [
                [0, 0, 0],
                [0, 0, 255],
                [0, 165, 255],
                [255, 0, 0],
                [255, 0, 255],
                [0, 255, 255],
                [0, 255, 0],
            ],
            dtype=np.uint8,
        )
        if self.num_classes <= len(base_palette):
            return base_palette[: self.num_classes].copy()

        palette = np.zeros((self.num_classes, 3), dtype=np.uint8)
        palette[: len(base_palette)] = base_palette
        for class_id in range(len(base_palette), self.num_classes):
            hue = int(180 * class_id / max(self.num_classes, 1))
            hsv_color = np.array([[[hue, 220, 255]]], dtype=np.uint8)
            palette[class_id] = cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0, 0]
        return palette

    def _preprocess(self, image_bgr: Any) -> Any:
        """执行 UNet 预处理，保持与模型项目 infer_camera_onnx.py 一致。"""

        import cv2
        import numpy as np

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_rgb = cv2.resize(
            image_rgb,
            (self.input_size, self.input_size),
            interpolation=cv2.INTER_LINEAR,
        )
        image_float = image_rgb.astype(np.float32) / 255.0
        mean = np.array(IMAGENET_MEAN, dtype=np.float32)
        std = np.array(IMAGENET_STD, dtype=np.float32)
        image_float = (image_float - mean) / std
        input_tensor = np.transpose(image_float, (2, 0, 1))
        return np.expand_dims(input_tensor, axis=0).astype(np.float32, copy=False)

    def _mask_to_color(self, mask: Any, palette: Any) -> Any:
        """把单通道类别 mask 转成彩色 BGR mask。"""

        import numpy as np

        safe_mask = np.clip(mask, 0, len(palette) - 1).astype(np.uint8)
        return palette[safe_mask]

    def _overlay_mask(self, image_bgr: Any, mask: Any, palette: Any, *, alpha: float = 0.45) -> Any:
        """把缺陷 mask 叠加到原始图像上。"""

        import cv2

        frame_h, frame_w = image_bgr.shape[:2]
        resized_mask = cv2.resize(
            mask.astype("uint8"),
            (frame_w, frame_h),
            interpolation=cv2.INTER_NEAREST,
        )
        color_mask = self._mask_to_color(resized_mask, palette)
        blended = cv2.addWeighted(image_bgr, 1.0 - alpha, color_mask, alpha, 0)
        defect_area = resized_mask > 0
        output = image_bgr.copy()
        output[defect_area] = blended[defect_area]
        return output

    def _count_class_pixels(self, mask: Any) -> dict[str, int]:
        """统计每个非背景类别的像素数量。"""

        import numpy as np

        counts: dict[str, int] = {}
        for class_id in range(1, self.num_classes):
            class_name = SEGMENT_CLASS_NAMES[class_id] if class_id < len(SEGMENT_CLASS_NAMES) else f"class_{class_id}"
            pixel_count = int(np.count_nonzero(mask == class_id))
            if pixel_count > 0:
                counts[class_name] = pixel_count
        return counts

    def predict(self, image_bgr: Any) -> SegmentationPrediction:
        """对图片执行 UNet 分割推理。

        参数:
            image_bgr: OpenCV BGR 图像。

        返回:
            返回缺陷像素数量、类别像素分布、overlay 图和 mask 图字节。
        """

        import numpy as np

        session = self._get_session()
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        input_tensor = self._preprocess(image_bgr)

        started = time.perf_counter()
        logits = session.run([output_name], {input_name: input_tensor})[0]
        inference_ms = (time.perf_counter() - started) * 1000.0
        if logits.ndim != 4:
            raise IntegrationError(
                code="cloud_detection_segment_output_invalid",
                message="UNet 模型输出维度异常，期望 (1,C,H,W)。",
                details={"shape": str(getattr(logits, "shape", ""))},
            )

        mask = np.argmax(logits, axis=1)[0].astype("uint8")
        defect_pixels = int(np.count_nonzero(mask))
        class_pixel_counts = self._count_class_pixels(mask)
        palette = self._build_palette()
        overlay = self._overlay_mask(image_bgr, mask, palette)
        color_mask = self._mask_to_color(mask, palette)
        overlay_bytes, overlay_type = _encode_image(overlay, extension=".jpg", content_type="image/jpeg")
        mask_bytes, mask_type = _encode_image(color_mask, extension=".png", content_type="image/png")

        return SegmentationPrediction(
            model_name="UNet-MobileNetV3",
            model_path=self.model_path,
            defect_pixels=defect_pixels,
            class_pixel_counts=class_pixel_counts,
            inference_ms=inference_ms,
            overlay_bytes=overlay_bytes,
            overlay_content_type=overlay_type,
            mask_bytes=mask_bytes,
            mask_content_type=mask_type,
        )


class CloudDetectionService:
    """运行云端本地 ONNX 检测，并生成可写回检测记录的结构化上下文。"""

    def __init__(
        self,
        *,
        cos_client: CosClient | None = None,
        classifier: CloudClassifier | None = None,
        segmenter: CloudSegmenter | None = None,
        settings: Settings | None = None,
        image_decoder: Callable[[bytes], Any] | None = None,
    ) -> None:
        """初始化云端检测服务。

        参数:
            cos_client: COS 客户端，负责读取板端图片和上传云端检测产物图。
            classifier: 可选分类模型封装；测试会注入假模型，生产默认懒加载 ONNX。
            segmenter: 可选分割模型封装；测试会注入假模型，生产默认懒加载 ONNX。
            settings: 当前运行配置。
            image_decoder: 图片解码函数；测试可注入轻量替身，避免依赖 OpenCV。
        """

        self.settings = settings or get_settings()
        self.cos_client = cos_client or CosClient()
        self.classifier = classifier or CloudClassifier(
            model_path=self.settings.cloud_detection_classifier_model_path,
        )
        self.segmenter = segmenter or CloudSegmenter(
            model_path=self.settings.cloud_detection_segment_model_path,
            num_classes=self.settings.cloud_detection_segment_num_classes,
        )
        self.image_decoder = image_decoder or decode_image_bytes

    def run_for_record(self, *, record: DetectionRecord, trigger: str) -> dict[str, Any]:
        """对单条检测记录执行云端检测。

        参数:
            record: 已加载文件列表的检测记录。
            trigger: 触发来源，例如 ``auto_after_upload`` 或 ``manual_rerun``。

        主要流程:
            1. 从记录文件中选择 source，缺失时退回 annotated。
            2. 通过 COS 客户端读取图片字节。
            3. 解码图片并分别执行分类、分割模型。
            4. 上传云端生成的 mask、overlay 和分类结果图到 COS。
            5. 合并两个模型结论，生成与 MP157 初检的对比信息。
            6. 返回能直接写入 ``cloud_detection_context`` 的 JSON 字典。

        返回:
            返回结构化云端检测上下文；失败时也返回 ``status="failed"`` 的可读上下文。
        """

        started_at = _utc_now()
        if not bool(getattr(self.settings, "cloud_detection_enabled", True)):
            return self._build_failed_context(
                trigger=trigger,
                source_file=None,
                started_at=started_at,
                message="云端检测已关闭，未运行本地模型。",
                status="skipped",
            )

        source_file = self._select_detection_source_file(record=record)
        if source_file is None:
            return self._build_failed_context(
                trigger=trigger,
                source_file=None,
                started_at=started_at,
                message="当前记录没有可用于检测的 source 或 annotated 图片。",
            )

        try:
            image_payload = self.cos_client.read_file_bytes(
                bucket_name=source_file.bucket_name,
                region=source_file.region,
                object_key=source_file.object_key,
                max_bytes=int(getattr(self.settings, "cloud_detection_max_image_bytes", 8 * 1024 * 1024)),
            )
            image_bytes = image_payload.get("data")
            if not isinstance(image_bytes, bytes):
                raise IntegrationError(
                    code="cloud_detection_image_bytes_invalid",
                    message="COS 返回的图片内容不是字节数据。",
                )

            image_bgr = self.image_decoder(image_bytes)
            classification = self.classifier.predict(image_bgr)
            segmentation = self.segmenter.predict(image_bgr)
            generated_files = self._upload_generated_images(
                record=record,
                source_file=source_file,
                classification=classification,
                segmentation=segmentation,
                started_at=started_at,
            )
            return self._build_success_context(
                record=record,
                trigger=trigger,
                source_file=source_file,
                classification=classification,
                segmentation=segmentation,
                generated_files=generated_files,
                started_at=started_at,
            )
        except AppError as exc:
            return self._build_failed_context(
                trigger=trigger,
                source_file=source_file,
                started_at=started_at,
                message=exc.message,
                error_code=exc.code,
            )
        except Exception as exc:  # noqa: BLE001
            return self._build_failed_context(
                trigger=trigger,
                source_file=source_file,
                started_at=started_at,
                message=f"云端检测运行异常：{exc}",
                error_code="cloud_detection_unhandled_error",
            )

    def _select_detection_source_file(self, *, record: DetectionRecord) -> FileObject | None:
        """选择云端检测使用的图片。

        参数:
            record: 检测记录，要求已包含 ``files`` 集合。

        返回:
            优先返回 source 图片；没有 source 时返回 annotated 图片；都没有时返回 None。
        """

        eligible_files = [
            file_object
            for file_object in getattr(record, "files", []) or []
            if file_object.file_kind in {FileKind.SOURCE, FileKind.ANNOTATED}
        ]
        if not eligible_files:
            return None

        def sort_key(file_object: FileObject) -> tuple[int, float, int]:
            """source 优先，同类型内选择最新上传的图片。"""

            kind_priority = 0 if file_object.file_kind == FileKind.SOURCE else 1
            uploaded_at = file_object.uploaded_at or file_object.created_at or datetime.min.replace(tzinfo=timezone.utc)
            return (kind_priority, -uploaded_at.timestamp(), -int(file_object.id or 0))

        return sorted(eligible_files, key=sort_key)[0]

    def _build_source_file_context(self, *, source_file: FileObject | None) -> dict[str, Any] | None:
        """把文件对象转换成 cloud_detection_context 中的 source_file 结构。"""

        if source_file is None:
            return None
        return {
            "file_id": source_file.id,
            "file_kind": source_file.file_kind.value,
            "bucket_name": source_file.bucket_name,
            "region": source_file.region,
            "object_key": source_file.object_key,
        }

    def _build_classification_context(self, *, prediction: ClassificationPrediction) -> dict[str, Any]:
        """把分类预测转换成可序列化上下文。"""

        good_probability = _group_probability(prediction.probabilities, group="good")
        bad_probability = _group_probability(prediction.probabilities, group="bad")
        return {
            "model_name": prediction.model_name,
            "model_path": prediction.model_path,
            "predicted_label": prediction.predicted_label,
            "predicted_result": resolve_result_from_label(prediction.predicted_label).value,
            "confidence": prediction.confidence,
            "good_probability": good_probability,
            "bad_probability": bad_probability,
            "probabilities": prediction.probabilities,
            "inference_ms": prediction.inference_ms,
        }

    def _build_segmentation_context(self, *, prediction: SegmentationPrediction) -> dict[str, Any]:
        """把分割预测转换成可序列化上下文。"""

        threshold_pixels = int(getattr(self.settings, "cloud_detection_defect_pixel_threshold", 80))
        predicted_result = DetectionResult.BAD if prediction.defect_pixels >= threshold_pixels else DetectionResult.GOOD
        return {
            "model_name": prediction.model_name,
            "model_path": prediction.model_path,
            "defect_pixels": prediction.defect_pixels,
            "threshold_pixels": threshold_pixels,
            "predicted_result": predicted_result.value,
            "class_pixel_counts": prediction.class_pixel_counts,
            "inference_ms": prediction.inference_ms,
        }

    def _resolve_cloud_result(
        self,
        *,
        classification_result: DetectionResult,
        segmentation_result: DetectionResult,
    ) -> DetectionResult:
        """合并分类和分割结论。

        规则:
            任一模型判为 bad 时，云端结论优先 bad；都为 good 时才返回 good；
            其它组合返回 uncertain，避免把未知标签强行当作良品。
        """

        if DetectionResult.BAD in {classification_result, segmentation_result}:
            return DetectionResult.BAD
        if {classification_result, segmentation_result} == {DetectionResult.GOOD}:
            return DetectionResult.GOOD
        return DetectionResult.UNCERTAIN

    def _build_comparison(self, *, record: DetectionRecord, cloud_result: DetectionResult) -> dict[str, Any]:
        """生成 MP157 初检与云端复检的对比结论。"""

        mp157_result = record.result
        is_conflict = mp157_result != cloud_result
        if is_conflict:
            suggested_action = "建议人工复核，并考虑修正板端结果。"
        elif cloud_result == DetectionResult.BAD:
            suggested_action = "云端与板端均倾向不良，建议按不良样本复核缺陷位置。"
        else:
            suggested_action = "云端与板端结论一致，可结合图片证据归档。"
        return {
            "mp157_result": mp157_result.value,
            "cloud_result": cloud_result.value,
            "is_conflict": is_conflict,
            "suggested_action": suggested_action,
        }

    def _build_summary_text(
        self,
        *,
        classification: ClassificationPrediction,
        segmentation: SegmentationPrediction,
        comparison: dict[str, Any],
    ) -> str:
        """生成操作员可直接阅读的中文摘要。"""

        good_probability = _group_probability(classification.probabilities, group="good")
        bad_probability = _group_probability(classification.probabilities, group="bad")
        threshold_pixels = int(getattr(self.settings, "cloud_detection_defect_pixel_threshold", 80))
        conflict_text = (
            f"云端结论 {comparison['cloud_result']} 与 MP157 初检 {comparison['mp157_result']} 不一致，"
            "建议人工复核并修正板端结果。"
            if comparison["is_conflict"]
            else f"云端结论 {comparison['cloud_result']} 与 MP157 初检一致。"
        )
        return (
            f"云端分类模型倾向 {classification.predicted_label}，"
            f"坏件概率 {_format_percent(bad_probability)}，良品概率 {_format_percent(good_probability)}；"
            f"UNet 检出疑似缺陷像素 {segmentation.defect_pixels}，"
            f"阈值 {threshold_pixels}。{conflict_text}"
        )

    def _build_generated_artifacts(
        self,
        *,
        classification: ClassificationPrediction,
        segmentation: SegmentationPrediction,
    ) -> list[GeneratedImageArtifact]:
        """整理本次云端检测生成的图片产物。"""

        artifacts: list[GeneratedImageArtifact] = []
        if segmentation.overlay_bytes:
            artifacts.append(
                GeneratedImageArtifact(
                    artifact_type="cloud_unet_overlay",
                    display_name="云端 UNet 缺陷叠加图",
                    file_kind=FileKind.ANNOTATED,
                    content_type=segmentation.overlay_content_type or "image/jpeg",
                    data=segmentation.overlay_bytes,
                )
            )
        if segmentation.mask_bytes:
            artifacts.append(
                GeneratedImageArtifact(
                    artifact_type="cloud_unet_mask",
                    display_name="云端 UNet 缺陷 mask 图",
                    file_kind=FileKind.ANNOTATED,
                    content_type=segmentation.mask_content_type or "image/png",
                    data=segmentation.mask_bytes,
                )
            )
        if classification.visualization_bytes:
            artifacts.append(
                GeneratedImageArtifact(
                    artifact_type="cloud_mobilenetv3_classification",
                    display_name="云端 MobileNetV3-Small 分类结果图",
                    file_kind=FileKind.ANNOTATED,
                    content_type=classification.visualization_content_type or "image/jpeg",
                    data=classification.visualization_bytes,
                )
            )
        return artifacts

    def _extension_for_content_type(self, content_type: str) -> str:
        """根据 MIME 类型返回对象扩展名。"""

        if content_type == "image/png":
            return "png"
        if content_type in {"image/jpeg", "image/jpg"}:
            return "jpg"
        return "bin"

    def _resolve_generated_target(self, *, source_file: FileObject) -> tuple[str, str]:
        """决定云端检测产物上传到哪个 bucket 和 region。"""

        bucket_name = str(getattr(self.settings, "cos_bucket", "") or "").strip() or source_file.bucket_name
        region = str(getattr(self.settings, "cos_region", "") or "").strip() or source_file.region
        return bucket_name, region

    def _upload_generated_images(
        self,
        *,
        record: DetectionRecord,
        source_file: FileObject,
        classification: ClassificationPrediction,
        segmentation: SegmentationPrediction,
        started_at: datetime,
    ) -> list[dict[str, Any]]:
        """上传云端检测生成的图片，并返回可写入上下文的元数据。

        参数:
            record: 当前检测记录。
            source_file: 本次检测使用的源图片。
            classification: 分类模型输出，可能包含分类结果图。
            segmentation: 分割模型输出，可能包含 mask 和 overlay 图。
            started_at: 本次检测开始时间；当前对象名固定，时间只保留在上下文里用于审计。

        返回:
            每个元素都是前端和后续 DB 登记可复用的文件元数据。
        """

        bucket_name, region = self._resolve_generated_target(source_file=source_file)
        generated_files: list[dict[str, Any]] = []

        for artifact in self._build_generated_artifacts(
            classification=classification,
            segmentation=segmentation,
        ):
            extension = self._extension_for_content_type(artifact.content_type)
            # 云端检测产物代表“当前最新复核结果”，不是历史版本归档。
            # 因此同一记录同一产物类型使用固定 COS key，手动重跑时由 COS 覆盖旧对象，
            # 详情页和 AI 引用也会继续指向当前结果图。
            object_key = f"detections/{record.record_no}/cloud_detection/{artifact.artifact_type}.{extension}"
            upload_result = self.cos_client.upload_file_bytes(
                bucket_name=bucket_name,
                region=region,
                object_key=object_key,
                data=artifact.data,
                content_type=artifact.content_type,
            )
            preview_url = self.cos_client.build_object_access_url(
                bucket_name=str(upload_result["bucket_name"]),
                region=str(upload_result["region"]),
                object_key=str(upload_result["object_key"]),
            )
            generated_files.append(
                {
                    "artifact_type": artifact.artifact_type,
                    "display_name": artifact.display_name,
                    "file_kind": artifact.file_kind.value,
                    "storage_provider": StorageProvider.COS.value,
                    "bucket_name": upload_result["bucket_name"],
                    "region": upload_result["region"],
                    "object_key": upload_result["object_key"],
                    "content_type": upload_result["content_type"],
                    "size_bytes": upload_result["size_bytes"],
                    "etag": upload_result.get("etag"),
                    "preview_url": preview_url,
                }
            )

        return generated_files

    def _build_success_context(
        self,
        *,
        record: DetectionRecord,
        trigger: str,
        source_file: FileObject,
        classification: ClassificationPrediction,
        segmentation: SegmentationPrediction,
        generated_files: list[dict[str, Any]],
        started_at: datetime,
    ) -> dict[str, Any]:
        """组装检测成功上下文。"""

        classification_result = resolve_result_from_label(classification.predicted_label)
        threshold_pixels = int(getattr(self.settings, "cloud_detection_defect_pixel_threshold", 80))
        segmentation_result = DetectionResult.BAD if segmentation.defect_pixels >= threshold_pixels else DetectionResult.GOOD
        cloud_result = self._resolve_cloud_result(
            classification_result=classification_result,
            segmentation_result=segmentation_result,
        )
        comparison = self._build_comparison(record=record, cloud_result=cloud_result)
        finished_at = _utc_now()

        return {
            "status": "success",
            "trigger": trigger,
            "source_file": self._build_source_file_context(source_file=source_file),
            "classification": self._build_classification_context(prediction=classification),
            "segmentation": self._build_segmentation_context(prediction=segmentation),
            "generated_files": generated_files,
            "comparison": comparison,
            "summary_text": self._build_summary_text(
                classification=classification,
                segmentation=segmentation,
                comparison=comparison,
            ),
            "started_at": _isoformat_utc(started_at),
            "finished_at": _isoformat_utc(finished_at),
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "error_message": None,
        }

    def _build_failed_context(
        self,
        *,
        trigger: str,
        source_file: FileObject | None,
        started_at: datetime,
        message: str,
        error_code: str | None = None,
        status: str = "failed",
    ) -> dict[str, Any]:
        """组装检测失败或跳过上下文。"""

        finished_at = _utc_now()
        readable_summary = message if message.startswith("云端检测") else f"云端检测失败：{message}"
        return {
            "status": status,
            "trigger": trigger,
            "source_file": self._build_source_file_context(source_file=source_file),
            "generated_files": [],
            "summary_text": readable_summary,
            "started_at": _isoformat_utc(started_at),
            "finished_at": _isoformat_utc(finished_at),
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "error_code": error_code,
            "error_message": message,
        }
