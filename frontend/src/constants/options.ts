import type {
  DetectionResult,
  DeviceStatus,
  DeviceType,
  ReviewStatus,
} from "@/types/api";

export interface SelectOption<TValue extends string | number> {
  readonly label: string;
  readonly value: TValue;
}

/**
 * 检测结果候选项。
 * 统一给记录创建、审核表单和状态筛选复用，避免页面里散落重复字面量。
 */
export const detectionResultOptions: SelectOption<DetectionResult>[] = [
  { label: "良品", value: "good" },
  { label: "坏品", value: "bad" },
  { label: "待确认", value: "uncertain" },
];

/**
 * 设备类型候选项。
 */
export const deviceTypeOptions: SelectOption<DeviceType>[] = [
  { label: "MP157", value: "mp157" },
  { label: "STM32F4", value: "f4" },
  { label: "网关", value: "gateway" },
  { label: "其他", value: "other" },
];

/**
 * 设备状态候选项。
 */
export const deviceStatusOptions: SelectOption<DeviceStatus>[] = [
  { label: "在线", value: "online" },
  { label: "离线", value: "offline" },
  { label: "故障", value: "fault" },
];

/**
 * 复核状态候选项。
 * 这里特意用“复核”而不是“审核”，强调 MP157 初检始终存在，
 * 人工与云端大模型只负责二次确认链路。
 */
export const reviewStatusOptions: SelectOption<ReviewStatus>[] = [
  { label: "待复核", value: "pending" },
  { label: "已复核", value: "reviewed" },
  { label: "AI 预留", value: "ai_reserved" },
];
