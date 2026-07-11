"""检测记录相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.db.models.enums import DetectionResult, ReviewStatus
from src.schemas.context_explanation import ContextExplanationResponse
from src.schemas.common import ORMBaseModel
from src.schemas.device import DeviceBrief
from src.schemas.part import PartBrief
from src.schemas.review import ReviewRecordResponse
from src.schemas.upload import FileObjectResponse


DETECTION_RESULT_ALIASES: dict[str, DetectionResult] = {
    # MP157 正常上报时仍建议使用英文稳定值；这里保留英文映射，便于统一走同一个归一化入口。
    "good": DetectionResult.GOOD,
    "bad": DetectionResult.BAD,
    "uncertain": DetectionResult.UNCERTAIN,
    # 兼容现场端或调试脚本可能直接上传的中文结论。
    "良品": DetectionResult.GOOD,
    "好品": DetectionResult.GOOD,
    "坏品": DetectionResult.BAD,
    "不良": DetectionResult.BAD,
    "不良品": DetectionResult.BAD,
    "待复核": DetectionResult.UNCERTAIN,
    "待确认": DetectionResult.UNCERTAIN,
    "不确定": DetectionResult.UNCERTAIN,
    # 板端回写协议里把云端 uncertain 映射为 review；反向接入时也归入待复核。
    "review": DetectionResult.UNCERTAIN,
    "复核": DetectionResult.UNCERTAIN,
}
"""检测结果输入别名字典。

键是 MP157、调试脚本或板端协议可能上传的原始文本，值是云端数据库持久化使用的稳定枚举。
这里只定义入口兼容关系，不改变数据库枚举和对外响应字段。
"""


def normalize_detection_result_alias(value: Any) -> Any:
    """将检测结果输入别名归一为 DetectionResult。

    主要流程：
    1. 已经是 DetectionResult 或 None 时直接返回，避免影响 Pydantic 对可空字段的处理；
    2. 字符串输入会先去掉首尾空白并转成小写，用于兼容英文大小写和现场脚本多余空格；
    3. 命中别名字典时返回稳定枚举，未命中时保留原值，让 Pydantic 继续给出标准枚举错误。

    参数:
        value: 请求体中 `result`、`surface_result`、`backlight_result` 或 `eddy_result` 的原始输入。

    返回:
        返回归一后的 DetectionResult；未知输入返回原值并交给后续校验处理。
    """

    if value is None or isinstance(value, DetectionResult):
        return value
    if not isinstance(value, str):
        return value

    normalized_value = value.strip().lower()
    return DETECTION_RESULT_ALIASES.get(normalized_value, value)


class DetectionRecordCreateRequest(BaseModel):
    """创建检测记录请求体。"""

    record_no: str | None = Field(default=None, max_length=64)
    part_id: int | None = Field(default=None, ge=1)
    part_code: str | None = Field(default=None, min_length=2, max_length=64)
    part_name: str | None = Field(default=None, min_length=1, max_length=128)
    part_category: str | None = Field(default=None, max_length=64)
    auto_create_part: bool = False
    device_id: int = Field(ge=1)
    result: DetectionResult
    review_status: ReviewStatus = ReviewStatus.PENDING
    surface_result: DetectionResult | None = None
    backlight_result: DetectionResult | None = None
    eddy_result: DetectionResult | None = None
    defect_type: str | None = Field(default=None, max_length=128)
    defect_desc: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    vision_context: dict[str, Any] | None = None
    sensor_context: dict[str, Any] | None = None
    decision_context: dict[str, Any] | None = None
    device_context: dict[str, Any] | None = None
    captured_at: datetime
    detected_at: datetime | None = None
    uploaded_at: datetime | None = None
    storage_last_modified: datetime | None = None

    @field_validator("result", "surface_result", "backlight_result", "eddy_result", mode="before")
    @classmethod
    def normalize_result_fields(cls, value: Any) -> Any:
        """归一化 MP157 上报的检测结果字段。

        主要流程：
        1. 在 Pydantic 枚举校验前接收原始输入；
        2. 调用统一别名函数，把中文“待复核/待确认”等现场端结果转成 `uncertain`；
        3. 未知输入不吞掉错误，继续由枚举校验返回清晰的 422。

        参数:
            value: 单个检测结果字段的原始输入值。

        返回:
            返回可被 DetectionResult 枚举接受的值，或原样返回未知值以触发标准校验错误。
        """

        return normalize_detection_result_alias(value)


class DetectionRecordListItem(ORMBaseModel):
    """检测记录列表项响应体。"""

    id: int
    record_no: str
    part_id: int
    device_id: int
    result: DetectionResult
    effective_result: DetectionResult
    review_status: ReviewStatus
    surface_result: DetectionResult | None
    backlight_result: DetectionResult | None
    eddy_result: DetectionResult | None
    defect_type: str | None
    defect_desc: str | None
    confidence_score: float | None
    vision_context: dict[str, Any] | None
    sensor_context: dict[str, Any] | None
    decision_context: dict[str, Any] | None
    device_context: dict[str, Any] | None
    captured_at: datetime
    detected_at: datetime | None
    uploaded_at: datetime | None
    storage_last_modified: datetime | None
    board_sync_status: str | None
    board_sync_time: datetime | None
    board_sync_error: str | None
    board_last_synced_review_id: int | None
    created_at: datetime
    updated_at: datetime
    part: PartBrief
    device: DeviceBrief


class DetectionRecordDetailResponse(DetectionRecordListItem):
    """检测记录详情响应体。"""

    context_explanations: ContextExplanationResponse | None = None
    files: list[FileObjectResponse]
    reviews: list[ReviewRecordResponse]


class DetectionRecordListResponse(BaseModel):
    """检测记录列表响应体。"""

    items: list[DetectionRecordListItem]
    total: int
    skip: int
    limit: int
