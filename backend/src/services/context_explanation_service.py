"""MP157 上下文字段中文解释服务。"""

from __future__ import annotations

from typing import Any

from src.schemas.context_explanation import (
    ContextExplanationGroup,
    ContextExplanationItem,
    ContextExplanationResponse,
)


# 结果类枚举的中文说明集中放在服务内，避免详情页、AI 和 PDF 各自翻译导致口径漂移。
DECISION_LABELS: dict[str, str] = {
    "pass": "通过",
    "fail": "不通过",
    "review": "需要复核",
    "unknown": "未知",
    "good": "良品",
    "bad": "不良品",
    "uncertain": "待确认",
}

# F4 流程中的下一步动作需要解释成现场能理解的操作语义。
NEXT_STEP_LABELS: dict[str, str] = {
    "upload_then_final_sort": "先上传云端，上传完成后再通知 F4 做最终分拣",
}

# 顶层上下文分组的中文标题和默认说明。
GROUP_META: dict[str, tuple[str, str]] = {
    "vision": ("视觉模型中文解释", "解释 MP157 视觉模型、分割结果和分类结果的含义。"),
    "sensor": ("传感器中文解释", "解释称重、LDC1614 涡流和 F4 联动流程上传的传感器含义。"),
    "decision": ("综合判定中文解释", "解释 MP157 为什么把当前样本判成良品、不良或待确认。"),
    "device": ("设备运行中文解释", "解释设备任务、样本编号和上传运行状态等现场信息。"),
}


def _is_plain_object(value: Any) -> bool:
    """判断值是否是可继续展开的普通字典。

    参数:
        value: 任意原始上下文字段值。

    返回:
        `True` 表示值是字典，可以继续按层级展开；其它值返回 `False`。
    """

    return isinstance(value, dict)


def _format_value(value: Any) -> str:
    """把原始字段值转换为适合展示和写入 PDF/AI 提示词的短文本。

    参数:
        value: MP157 上传的原始字段值，可能是字符串、数字、布尔值、空值、数组或字典。

    返回:
        返回中文友好的短文本；复杂结构会退回到字符串表示，保留排障线索。
    """

    if value is None:
        return "未提供"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, (int, str)):
        return str(value) if str(value) else "未提供"
    if isinstance(value, list):
        if not value:
            return "空列表"
        return " / ".join(_format_value(item) for item in value)
    return str(value)


def _decision_label(value: Any) -> str:
    """把 pass/fail/good/bad 等稳定枚举值转成中文结论。

    参数:
        value: 原始判定字段，通常来自 MP157/F4 上传的英文枚举。

    返回:
        返回中文结论；未知值保留原文，避免隐藏现场新增枚举。
    """

    normalized_value = str(value).strip().lower()
    return DECISION_LABELS.get(normalized_value, _format_value(value))


def _boolean_status(value: Any, *, true_text: str, false_text: str) -> str:
    """把布尔状态转换成指定的中文短语。

    参数:
        value: 原始布尔字段。
        true_text: 值为真时的中文说明。
        false_text: 值为假时的中文说明。

    返回:
        返回匹配状态的中文短语；非布尔值使用通用格式化结果。
    """

    if isinstance(value, bool):
        return true_text if value else false_text
    return _format_value(value)


def _make_item(
    *,
    source_path: str,
    label: str,
    value: Any,
    explanation: str,
) -> ContextExplanationItem:
    """创建一条上下文解释项。

    参数:
        source_path: 原始 JSON 中的完整字段路径，便于从解释反查原始数据。
        label: 中文短标签，用于 UI 和 PDF 卡片标题。
        value: 原始字段值。
        explanation: 面向操作员的完整中文解释。

    返回:
        返回 `ContextExplanationItem`，其中 `value_text` 已经格式化为可读文本。
    """

    return ContextExplanationItem(
        source_path=source_path,
        label=label,
        value_text=_format_value(value),
        explanation=explanation,
    )


def _fallback_label(path_parts: list[str]) -> str:
    """把未知字段路径转换为可读的中文调试标签。

    参数:
        path_parts: 不含顶层 context 名称的字段路径片段。

    返回:
        返回“原始字段 xxx”形式的标签，提醒用户这是未建模的排障字段。
    """

    return f"原始字段 {'.'.join(path_parts)}"


def _fallback_item(*, source_path: str, path_parts: list[str], value: Any) -> ContextExplanationItem:
    """为暂未显式建模的字段生成兜底解释。

    参数:
        source_path: 原始 JSON 完整字段路径。
        path_parts: 不含顶层 context 名称的字段路径片段。
        value: 原始字段值。

    返回:
        返回不会丢数据的兜底解释项，便于后续根据现场数据补充规则。
    """

    label = _fallback_label(path_parts)
    return _make_item(
        source_path=source_path,
        label=label,
        value=value,
        explanation=f"{label}：{_format_value(value)}。这是 MP157 上传的原始调试字段，当前云端暂未绑定专门业务解释。",
    )


def _flatten_unknown_fields(
    *,
    context_prefix: str,
    value: Any,
    path_parts: list[str],
) -> list[ContextExplanationItem]:
    """递归展开未知结构，保证新增字段不会在解释结果中丢失。

    参数:
        context_prefix: 顶层上下文名称，例如 `sensor_context`。
        value: 当前层级的原始值。
        path_parts: 当前字段路径片段。

    返回:
        返回兜底解释项列表。
    """

    if _is_plain_object(value):
        items: list[ContextExplanationItem] = []
        for child_key, child_value in value.items():
            items.extend(
                _flatten_unknown_fields(
                    context_prefix=context_prefix,
                    value=child_value,
                    path_parts=[*path_parts, str(child_key)],
                )
            )
        return items

    if isinstance(value, list) and any(_is_plain_object(item) for item in value):
        items = []
        for index, child_value in enumerate(value):
            items.extend(
                _flatten_unknown_fields(
                    context_prefix=context_prefix,
                    value=child_value,
                    path_parts=[*path_parts, f"[{index}]"],
                )
            )
        return items

    source_path = ".".join([context_prefix, *path_parts])
    return [_fallback_item(source_path=source_path, path_parts=path_parts, value=value)]


def _explain_vision_context(vision_context: dict[str, Any] | None) -> list[ContextExplanationItem]:
    """解释视觉上下文中的 MobileNetV3-Small 与 UNet 字段。

    参数:
        vision_context: MP157 上传的 `vision_context` 原始字典。

    返回:
        返回视觉相关解释项；空上下文返回空列表。
    """

    if not vision_context:
        return []

    items: list[ContextExplanationItem] = []
    handled_paths: set[str] = set()
    unet_context = vision_context.get("unet")
    mobilenet_context = vision_context.get("mobilenetv3_small")

    if isinstance(unet_context, dict):
        if "defect_pixels" in unet_context:
            handled_paths.add("unet.defect_pixels")
            defect_pixels = unet_context["defect_pixels"]
            items.append(
                _make_item(
                    source_path="vision_context.unet.defect_pixels",
                    label="UNet 缺陷像素数",
                    value=defect_pixels,
                    explanation=f"UNet 检出缺陷像素数：{_format_value(defect_pixels)}，低于阈值时通常认为没有明显分割缺陷。",
                )
            )
        if "threshold_pixels" in unet_context:
            handled_paths.add("unet.threshold_pixels")
            threshold_pixels = unet_context["threshold_pixels"]
            items.append(
                _make_item(
                    source_path="vision_context.unet.threshold_pixels",
                    label="UNet 缺陷像素阈值",
                    value=threshold_pixels,
                    explanation=f"UNet 缺陷像素阈值：{_format_value(threshold_pixels)}，用于判断分割缺陷面积是否达到不良条件。",
                )
            )

    if isinstance(mobilenet_context, dict):
        if "class_label" in mobilenet_context:
            handled_paths.add("mobilenetv3_small.class_label")
            class_label = mobilenet_context["class_label"]
            items.append(
                _make_item(
                    source_path="vision_context.mobilenetv3_small.class_label",
                    label="MobileNetV3-Small 分类标签",
                    value=class_label,
                    explanation=f"MobileNetV3-Small 分类标签：{_format_value(class_label)}，表示视觉分类模型给出的零件类别和 good/bad 倾向。",
                )
            )
        if "confidence" in mobilenet_context:
            handled_paths.add("mobilenetv3_small.confidence")
            confidence = mobilenet_context["confidence"]
            items.append(
                _make_item(
                    source_path="vision_context.mobilenetv3_small.confidence",
                    label="MobileNetV3-Small 置信度",
                    value=confidence,
                    explanation=f"MobileNetV3-Small 置信度：{_format_value(confidence)}，数值越高表示分类模型越确信当前判断。",
                )
            )

    items.extend(
        _collect_unhandled_top_level_items(
            context_prefix="vision_context",
            context=vision_context,
            handled_paths=handled_paths,
        )
    )
    return items


def _explain_weighing_context(weighing_context: dict[str, Any]) -> list[ContextExplanationItem]:
    """解释 HX711 称重模块字段。

    参数:
        weighing_context: `sensor_context.weighing` 原始字典。

    返回:
        返回称重相关解释项。
    """

    items: list[ContextExplanationItem] = []
    if "stable" in weighing_context:
        stable = weighing_context["stable"]
        items.append(
            _make_item(
                source_path="sensor_context.weighing.stable",
                label="称重稳定状态",
                value=stable,
                explanation=f"称重稳定状态：{_boolean_status(stable, true_text='已稳定', false_text='未稳定')}，未稳定时重量结果通常不建议直接用于最终判定。",
            )
        )
    if "decision" in weighing_context:
        decision = weighing_context["decision"]
        items.append(
            _make_item(
                source_path="sensor_context.weighing.decision",
                label="称重结论",
                value=decision,
                explanation=f"称重结论：{_decision_label(decision)}，重量传感器认为该样本是否在允许范围内。",
            )
        )
    if "raw_adc" in weighing_context:
        raw_adc = weighing_context["raw_adc"]
        items.append(
            _make_item(
                source_path="sensor_context.weighing.raw_adc",
                label="HX711 原始 ADC",
                value=raw_adc,
                explanation=f"HX711 原始 ADC 读数：{_format_value(raw_adc)}，用于换算重量，通常给排障和标定使用。",
            )
        )
    if "net_weight_g" in weighing_context:
        net_weight = weighing_context["net_weight_g"]
        items.append(
            _make_item(
                source_path="sensor_context.weighing.net_weight_g",
                label="净重",
                value=net_weight,
                explanation=f"称重净重：{_format_value(net_weight)} g，表示扣除皮重后的样本重量。",
            )
        )
    if "gross_weight_g" in weighing_context:
        gross_weight = weighing_context["gross_weight_g"]
        items.append(
            _make_item(
                source_path="sensor_context.weighing.gross_weight_g",
                label="毛重",
                value=gross_weight,
                explanation=f"称重毛重：{_format_value(gross_weight)} g，表示未扣除皮重前的重量读数。",
            )
        )
    return items


def _explain_ldc_context(ldc_context: dict[str, Any]) -> list[ContextExplanationItem]:
    """解释 LDC1614 涡流/电感检测字段。

    参数:
        ldc_context: `sensor_context.ldc1614_eddy_current` 原始字典。

    返回:
        返回整体判定和各通道解释项。
    """

    items: list[ContextExplanationItem] = []
    if "overall_decision" in ldc_context:
        overall_decision = ldc_context["overall_decision"]
        items.append(
            _make_item(
                source_path="sensor_context.ldc1614_eddy_current.overall_decision",
                label="LDC1614 总体结论",
                value=overall_decision,
                explanation=f"LDC1614 总体结论：{_decision_label(overall_decision)}，表示涡流/电感检测对当前样本的综合判断。",
            )
        )
    if "status" in ldc_context:
        status = ldc_context["status"]
        items.append(
            _make_item(
                source_path="sensor_context.ldc1614_eddy_current.status",
                label="LDC1614 状态",
                value=status,
                explanation=f"LDC1614 状态：{_format_value(status)}，用于判断本次涡流/电感采集流程是否正常完成。",
            )
        )

    channels = ldc_context.get("channels")
    if isinstance(channels, list):
        for index, channel in enumerate(channels):
            if not isinstance(channel, dict):
                continue
            channel_id = channel.get("channel", index)
            channel_prefix = f"sensor_context.ldc1614_eddy_current.channels[{index}]"
            if "enabled" in channel:
                enabled = channel["enabled"]
                state_text = _boolean_status(enabled, true_text="已启用", false_text="未启用")
                items.append(
                    _make_item(
                        source_path=f"{channel_prefix}.enabled",
                        label=f"LDC1614 通道 {channel_id} 启用状态",
                        value=enabled,
                        explanation=f"LDC1614 通道 {channel_id}：{state_text}，本次{'参与' if enabled is True else '不参与'}电感/涡流判定。",
                    )
                )
            if "raw_code" in channel:
                raw_code = channel["raw_code"]
                items.append(
                    _make_item(
                        source_path=f"{channel_prefix}.raw_code",
                        label=f"LDC1614 通道 {channel_id} 原始码值",
                        value=raw_code,
                        explanation=f"LDC1614 通道 {channel_id} 原始码值：{_format_value(raw_code)}，用于分析金属接近、电感变化或探头状态。",
                    )
                )
            if "delta_raw_code" in channel:
                delta_raw_code = channel["delta_raw_code"]
                items.append(
                    _make_item(
                        source_path=f"{channel_prefix}.delta_raw_code",
                        label=f"LDC1614 通道 {channel_id} 码值变化",
                        value=delta_raw_code,
                        explanation=f"LDC1614 通道 {channel_id} 码值变化：{_format_value(delta_raw_code)}，变化过大时通常提示形变、材质或位置异常。",
                    )
                )
            if "decision" in channel:
                channel_decision = channel["decision"]
                items.append(
                    _make_item(
                        source_path=f"{channel_prefix}.decision",
                        label=f"LDC1614 通道 {channel_id} 结论",
                        value=channel_decision,
                        explanation=f"LDC1614 通道 {channel_id} 结论：{_decision_label(channel_decision)}，表示该通道单独看是否支持放行。",
                    )
                )
    return items


def _explain_f4_flow_context(f4_context: dict[str, Any]) -> list[ContextExplanationItem]:
    """解释 MP157 与 F4 协同检测流程字段。

    参数:
        f4_context: `sensor_context.f4_flow` 原始字典。

    返回:
        返回 F4 握手、超时、传感器回传和下一步动作解释项。
    """

    items: list[ContextExplanationItem] = []
    if "model_ready_ack" in f4_context:
        model_ready_ack = f4_context["model_ready_ack"]
        items.append(
            _make_item(
                source_path="sensor_context.f4_flow.model_ready_ack",
                label="F4 模型就绪确认",
                value=model_ready_ack,
                explanation=f"F4 模型就绪确认：{_boolean_status(model_ready_ack, true_text='已收到', false_text='未收到')}，用于判断 F4 是否已经准备好进入本轮联动流程。",
            )
        )
    if "arm_job_start_ack" in f4_context:
        arm_job_start_ack = f4_context["arm_job_start_ack"]
        items.append(
            _make_item(
                source_path="sensor_context.f4_flow.arm_job_start_ack",
                label="F4 作业开始确认",
                value=arm_job_start_ack,
                explanation=f"F4 作业开始确认：{_boolean_status(arm_job_start_ack, true_text='已收到', false_text='未收到')}，用于确认机械臂或下位机流程是否已启动。",
            )
        )
    if "active_frame_timeout_ms" in f4_context:
        timeout_ms = f4_context["active_frame_timeout_ms"]
        items.append(
            _make_item(
                source_path="sensor_context.f4_flow.active_frame_timeout_ms",
                label="F4 有效帧等待超时",
                value=timeout_ms,
                explanation=f"F4 有效帧等待超时：{_format_value(timeout_ms)} ms，超过该时间仍未收到有效帧时需要检查串口通信或下位机状态。",
            )
        )
    if "weight_result_received" in f4_context:
        weight_received = f4_context["weight_result_received"]
        items.append(
            _make_item(
                source_path="sensor_context.f4_flow.weight_result_received",
                label="F4 称重结果回传",
                value=weight_received,
                explanation=f"F4 称重结果回传：{_boolean_status(weight_received, true_text='已收到', false_text='未收到')}，未收到时综合判定可能缺少重量依据。",
            )
        )
    if "ldc_result_received" in f4_context:
        ldc_received = f4_context["ldc_result_received"]
        items.append(
            _make_item(
                source_path="sensor_context.f4_flow.ldc_result_received",
                label="F4 涡流结果回传",
                value=ldc_received,
                explanation=f"F4 涡流结果回传：{_boolean_status(ldc_received, true_text='已收到', false_text='未收到')}，未收到时综合判定可能缺少 LDC1614 依据。",
            )
        )
    if "next_step" in f4_context:
        next_step = f4_context["next_step"]
        next_step_text = NEXT_STEP_LABELS.get(str(next_step), _format_value(next_step))
        items.append(
            _make_item(
                source_path="sensor_context.f4_flow.next_step",
                label="F4 下一步",
                value=next_step,
                explanation=f"下一步：{next_step_text}。",
            )
        )
    return items


def _explain_sensor_context(sensor_context: dict[str, Any] | None) -> list[ContextExplanationItem]:
    """解释传感器上下文中的称重、LDC1614 和 F4 流程字段。

    参数:
        sensor_context: MP157 上传的 `sensor_context` 原始字典。

    返回:
        返回传感器相关解释项。
    """

    if not sensor_context:
        return []

    items: list[ContextExplanationItem] = []
    weighing_context = sensor_context.get("weighing")
    ldc_context = sensor_context.get("ldc1614_eddy_current")
    f4_context = sensor_context.get("f4_flow")

    if isinstance(weighing_context, dict):
        items.extend(_explain_weighing_context(weighing_context))
    if isinstance(ldc_context, dict):
        items.extend(_explain_ldc_context(ldc_context))
    if isinstance(f4_context, dict):
        items.extend(_explain_f4_flow_context(f4_context))

    # 已显式解释的字段按完整路径去重；同一模块里的新增字段仍走兜底解释，避免“认识模块但漏掉字段”。
    handled_paths = {
        item.source_path.removeprefix("sensor_context.")
        for item in items
    }
    if any(path.startswith("ldc1614_eddy_current.channels[") for path in handled_paths):
        handled_paths.add("ldc1614_eddy_current.channels")
    items.extend(
        _collect_unhandled_top_level_items(
            context_prefix="sensor_context",
            context=sensor_context,
            handled_paths=handled_paths,
        )
    )
    return items


def _explain_decision_context(decision_context: dict[str, Any] | None) -> list[ContextExplanationItem]:
    """解释综合判定上下文字段。

    参数:
        decision_context: MP157 上传的 `decision_context` 原始字典。

    返回:
        返回综合判定相关解释项。
    """

    if not decision_context:
        return []

    items: list[ContextExplanationItem] = []
    handled_paths: set[str] = set()
    if "result" in decision_context:
        handled_paths.add("result")
        result = decision_context["result"]
        items.append(
            _make_item(
                source_path="decision_context.result",
                label="综合判定结果",
                value=result,
                explanation=f"综合判定：{_decision_label(result)}，这是 MP157 汇总视觉、称重、涡流和流程状态后给出的当前样本结论。",
            )
        )
    if "need_ai_review" in decision_context:
        handled_paths.add("need_ai_review")
        need_ai_review = decision_context["need_ai_review"]
        items.append(
            _make_item(
                source_path="decision_context.need_ai_review",
                label="是否建议 AI 复核",
                value=need_ai_review,
                explanation=f"是否建议 AI 复核：{_boolean_status(need_ai_review, true_text='建议', false_text='不建议')}，用于提示云端是否优先让 AI 或人工再看一次。",
            )
        )
    if "decision_rule" in decision_context:
        handled_paths.add("decision_rule")
        decision_rule = decision_context["decision_rule"]
        items.append(
            _make_item(
                source_path="decision_context.decision_rule",
                label="综合判定规则",
                value=decision_rule,
                explanation=f"综合判定规则：{_format_value(decision_rule)}，说明 MP157 当前使用哪套规则合并多路检测结果。",
            )
        )

    items.extend(
        _collect_unhandled_top_level_items(
            context_prefix="decision_context",
            context=decision_context,
            handled_paths=handled_paths,
        )
    )
    return items


def _explain_device_context(device_context: dict[str, Any] | None) -> list[ContextExplanationItem]:
    """解释设备运行上下文字段。

    参数:
        device_context: MP157 上传的 `device_context` 原始字典。

    返回:
        返回设备运行相关解释项。
    """

    if not device_context:
        return []

    items: list[ContextExplanationItem] = []
    handled_paths: set[str] = set()
    device_labels = {
        "device_code": "设备编号",
        "firmware_version": "固件版本",
        "cycle_id": "检测循环编号",
        "sample_id": "样本编号",
        "job_id": "F4 作业编号",
        "class_label": "视觉分类标签",
        "source_path": "本地源图路径",
    }
    for key, label in device_labels.items():
        if key not in device_context:
            continue
        handled_paths.add(key)
        value = device_context[key]
        items.append(
            _make_item(
                source_path=f"device_context.{key}",
                label=label,
                value=value,
                explanation=f"{label}：{_format_value(value)}，用于把云端记录追溯回 MP157 本机任务、样本或文件来源。",
            )
        )

    items.extend(
        _collect_unhandled_top_level_items(
            context_prefix="device_context",
            context=device_context,
            handled_paths=handled_paths,
        )
    )
    return items


def _collect_unhandled_top_level_items(
    *,
    context_prefix: str,
    context: dict[str, Any],
    handled_paths: set[str],
) -> list[ContextExplanationItem]:
    """收集顶层未处理字段的兜底解释。

    参数:
        context_prefix: 顶层上下文字段名称。
        context: 当前上下文字典。
        handled_paths: 已由显式规则处理的顶层字段或点分路径。

    返回:
        返回未处理字段的兜底解释项。
    """

    items: list[ContextExplanationItem] = []
    for key, value in context.items():
        key_text = str(key)
        if key_text in handled_paths:
            continue
        if any(path.startswith(f"{key_text}.") for path in handled_paths):
            if isinstance(value, dict):
                nested_items = []
                for child_key, child_value in value.items():
                    child_path = f"{key_text}.{child_key}"
                    if child_path in handled_paths:
                        continue
                    nested_items.extend(
                        _flatten_unknown_fields(
                            context_prefix=context_prefix,
                            value=child_value,
                            path_parts=[key_text, str(child_key)],
                        )
                    )
                items.extend(nested_items)
            continue
        items.extend(
            _flatten_unknown_fields(
                context_prefix=context_prefix,
                value=value,
                path_parts=[key_text],
            )
        )
    return items


def _build_group(*, key: str, items: list[ContextExplanationItem]) -> ContextExplanationGroup:
    """根据解释项构造分组摘要。

    参数:
        key: 分组稳定键，例如 `sensor`。
        items: 该分组下的解释项。

    返回:
        返回包含标题、摘要和解释项的分组对象。
    """

    title, default_summary = GROUP_META[key]
    if not items:
        summary = "MP157 本次没有上报这部分上下文。"
    else:
        preview_text = "；".join(item.explanation for item in items[:3])
        summary = preview_text if preview_text else default_summary
    return ContextExplanationGroup(
        key=key,
        title=title,
        summary=summary,
        items=items,
    )


def build_context_explanations(
    *,
    vision_context: dict[str, Any] | None,
    sensor_context: dict[str, Any] | None,
    decision_context: dict[str, Any] | None,
    device_context: dict[str, Any] | None,
) -> ContextExplanationResponse:
    """把 MP157 上传的四类上下文转换成统一中文解释。

    参数:
        vision_context: 原始视觉模型上下文。
        sensor_context: 原始称重、LDC1614 和 F4 流程上下文。
        decision_context: 原始综合判定上下文。
        device_context: 原始设备运行上下文。

    返回:
        返回统一解释响应；详情页、AI 提示词和 PDF 都应复用这个结果。
    """

    groups = [
        _build_group(key="vision", items=_explain_vision_context(vision_context)),
        _build_group(key="sensor", items=_explain_sensor_context(sensor_context)),
        _build_group(key="decision", items=_explain_decision_context(decision_context)),
        _build_group(key="device", items=_explain_device_context(device_context)),
    ]
    non_empty_groups = [group for group in groups if group.items]
    if not non_empty_groups:
        summary = "MP157 本次没有上报可解释的结构化上下文。"
    else:
        summary = f"已将 MP157 上报的 {len(non_empty_groups)} 类上下文转换为中文解释，可用于详情页、AI 分析和 PDF 报表。"

    return ContextExplanationResponse(summary=summary, groups=groups)
