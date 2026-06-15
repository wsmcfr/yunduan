import { describe, expect, it } from "vitest";

import {
  mapAIRecordContextDto,
  mapDetectionRecordDetailDto,
} from "@/services/mappers/commonMappers";
import type { AIRecordContextDto, DetectionRecordDetailDto } from "@/types/api";

/**
 * 构造包含云端检测上下文的最小检测记录详情 DTO。
 *
 * 返回:
 *   能覆盖 detection-record mapper 的后端 snake_case 响应对象。
 */
function buildDetectionRecordDetailDto(): DetectionRecordDetailDto {
  return {
    id: 13,
    record_no: "REC-CLOUD-001",
    part_id: 1,
    device_id: 2,
    result: "good",
    effective_result: "good",
    review_status: "pending",
    surface_result: null,
    backlight_result: null,
    eddy_result: null,
    defect_type: null,
    defect_desc: null,
    confidence_score: 0.86,
    vision_context: null,
    sensor_context: null,
    decision_context: null,
    device_context: null,
    cloud_detection_context: {
      status: "success",
      summary_text: "云端模型检测完成：分类和分割均倾向良品。",
      generated_files: [
        {
          artifact_type: "cloud_unet_overlay",
          display_name: "云端 UNet 缺陷叠加图",
          object_key: "detections/REC-CLOUD-001/cloud_detection/cloud_unet_overlay.jpg",
        },
      ],
    },
    captured_at: "2026-06-15T02:00:00.000Z",
    detected_at: "2026-06-15T02:00:01.000Z",
    uploaded_at: "2026-06-15T02:00:02.000Z",
    storage_last_modified: null,
    board_sync_status: null,
    board_sync_time: null,
    board_sync_error: null,
    board_last_synced_review_id: null,
    created_at: "2026-06-15T02:00:02.000Z",
    updated_at: "2026-06-15T02:00:02.000Z",
    part: {
      id: 1,
      part_code: "PART-001",
      name: "测试零件",
      category: "金属件",
    },
    device: {
      id: 2,
      device_code: "MP157-001",
      name: "MP157 视觉节点",
    },
    files: [],
    reviews: [],
  };
}

/**
 * 构造包含云端检测上下文的最小 AI 记录上下文 DTO。
 *
 * 返回:
 *   能覆盖 AIRecordContext mapper 的后端 snake_case 响应对象。
 */
function buildAIRecordContextDto(): AIRecordContextDto {
  return {
    record_id: 13,
    record_no: "REC-CLOUD-001",
    part_name: "测试零件",
    part_code: "PART-001",
    device_name: "MP157 视觉节点",
    device_code: "MP157-001",
    result: "good",
    effective_result: "good",
    review_status: "pending",
    defect_type: null,
    defect_desc: null,
    confidence_score: 0.86,
    vision_context: null,
    sensor_context: null,
    decision_context: null,
    device_context: null,
    cloud_detection_context: {
      status: "success",
      summary_text: "云端模型检测完成：分类和分割均倾向良品。",
    },
    captured_at: "2026-06-15T02:00:00.000Z",
    detected_at: "2026-06-15T02:00:01.000Z",
    uploaded_at: "2026-06-15T02:00:02.000Z",
    storage_last_modified: null,
    file_count: 0,
    review_count: 0,
    available_file_kinds: [],
    latest_review_decision: null,
    latest_review_comment: null,
    latest_reviewed_at: null,
  };
}

describe("cloud detection context mapper", () => {
  it("maps detection record cloud_detection_context to cloudDetectionContext", () => {
    const model = mapDetectionRecordDetailDto(buildDetectionRecordDetailDto());

    expect(model.cloudDetectionContext?.summary_text).toBe(
      "云端模型检测完成：分类和分割均倾向良品。",
    );
    expect(model.cloudDetectionContext?.generated_files).toHaveLength(1);
  });

  it("maps AI context cloud_detection_context to cloudDetectionContext", () => {
    const model = mapAIRecordContextDto(buildAIRecordContextDto());

    expect(model.cloudDetectionContext?.status).toBe("success");
    expect(model.cloudDetectionContext?.summary_text).toContain("云端模型检测完成");
  });
});
