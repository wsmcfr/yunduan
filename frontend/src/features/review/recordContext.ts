import type { StructuredContextBlock, StructuredContextValue } from "@/types/models";

export interface StructuredContextEntry {
  keyPath: string;
  label: string;
  valueText: string;
}

const structuredContextLabelMap: Record<string, string> = {
  model_name: "模型名称",
  model_version: "模型版本",
  model_identifier: "模型标识",
  channel_name: "通道名称",
  channel_result: "通道结果",
  surface_result: "表面结果",
  backlight_result: "背光通道结果",
  eddy_result: "涡流结果",
  score: "评分",
  confidence: "置信度",
  confidence_score: "置信度",
  threshold: "阈值",
  threshold_low: "下阈值",
  threshold_high: "上阈值",
  raw_value: "原始值",
  raw_inductance: "原始电感",
  normalized_value: "归一化值",
  computed_result: "计算结果",
  risk_level: "风险等级",
  decision_source: "判定来源",
  decision_reason: "判定原因",
  final_reason: "最终原因",
  batch_no: "批次号",
  task_no: "任务号",
  work_order_no: "工单号",
  firmware_version: "固件版本",
  capture_profile: "采集参数",
  camera_exposure: "曝光参数",
  operator_name: "操作员",
  upload_mode: "上传方式",
  sensor_name: "传感器名称",
  sensor_value: "传感器值",
  sensor_unit: "传感器单位",
  defect_region: "缺陷区域",
  defect_regions: "缺陷区域",
  defect_score: "缺陷评分",
  decision_trace: "判定链路",
  pass_rule: "放行规则",
  reject_rule: "拦截规则",
  cloud_detection_context: "云端模型检测上下文",
  status: "状态",
  trigger: "触发方式",
  source_file: "检测源图",
  classification: "MobileNetV3-Small 分类",
  segmentation: "UNet 分割",
  comparison: "云端与板端对比",
  generated_files: "云端生成图",
  summary_text: "云端检测摘要",
  started_at: "开始时间",
  finished_at: "完成时间",
  duration_ms: "耗时毫秒",
  error_code: "错误码",
  error_message: "错误信息",
  model_path: "模型路径",
  predicted_label: "预测标签",
  predicted_result: "预测结果",
  good_probability: "良品概率",
  bad_probability: "坏件概率",
  probabilities: "分类概率",
  inference_ms: "推理耗时毫秒",
  defect_pixels: "缺陷像素数",
  threshold_pixels: "缺陷阈值像素",
  class_pixel_counts: "类别像素统计",
  mp157_result: "MP157 初检结果",
  cloud_result: "云端检测结果",
  is_conflict: "是否冲突",
  suggested_action: "建议操作",
  artifact_type: "产物类型",
  display_name: "显示名称",
  object_key: "COS 路径",
  preview_url: "预览地址",
};

/**
 * 判断当前值是否属于可递归展开的普通对象。
 */
function isStructuredObject(value: StructuredContextValue): value is StructuredContextBlock {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * 将字段名转换成更适合普通人阅读的中文标签。
 * 未命中的字段也会做基础格式化，避免直接展示生硬的 snake_case。
 */
function formatStructuredContextLabel(key: string): string {
  if (structuredContextLabelMap[key]) {
    return structuredContextLabelMap[key];
  }

  return key
    .split("_")
    .filter(Boolean)
    .map((segment) => `${segment.slice(0, 1).toUpperCase()}${segment.slice(1)}`)
    .join(" ");
}

/**
 * 把结构化值转成页面可直接显示的文本。
 */
function formatStructuredContextValue(value: StructuredContextValue): string {
  if (value === null) {
    return "未提供";
  }

  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }

  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }

  if (typeof value === "string") {
    return value || "未提供";
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "空列表";
    }

    if (value.every((item) => !isStructuredObject(item) && !Array.isArray(item))) {
      return value.map((item) => formatStructuredContextValue(item)).join(" / ");
    }

    return JSON.stringify(value, null, 2);
  }

  return JSON.stringify(value, null, 2);
}

/**
 * 将结构化上下文拍平成展示项列表。
 * 页面层不需要知道原始 JSON 的层级细节，只消费拍平后的标签和值。
 */
export function flattenStructuredContext(
  context: StructuredContextBlock | null | undefined,
  parentKeys: string[] = [],
): StructuredContextEntry[] {
  if (!context) {
    return [];
  }

  const entries: StructuredContextEntry[] = [];

  for (const [key, value] of Object.entries(context)) {
    const nextKeys = [...parentKeys, key];
    const keyPath = nextKeys.join(".");
    const label = nextKeys.map((item) => formatStructuredContextLabel(item)).join(" / ");

    if (isStructuredObject(value) && Object.keys(value).length > 0) {
      entries.push(...flattenStructuredContext(value, nextKeys));
      continue;
    }

    entries.push({
      keyPath,
      label,
      valueText: formatStructuredContextValue(value),
    });
  }

  return entries;
}
