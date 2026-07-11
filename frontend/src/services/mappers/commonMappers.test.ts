import { describe, expect, it } from "vitest";

import { mapDetectionRecordDetailDto } from "@/services/mappers/commonMappers";
import type { DetectionRecordDetailDto } from "@/types/api";

describe("common mappers context explanations", () => {
  it("maps detection detail context explanations from snake_case to camelCase", () => {
    const dto: DetectionRecordDetailDto = {
      id: 1,
      record_no: "REC-MP157-0001",
      part_id: 1,
      device_id: 1,
      result: "bad",
      effective_result: "bad",
      review_status: "pending",
      surface_result: null,
      backlight_result: null,
      eddy_result: null,
      defect_type: "划痕",
      defect_desc: null,
      confidence_score: 0.91,
      vision_context: null,
      sensor_context: null,
      decision_context: null,
      device_context: null,
      captured_at: "2026-07-10T10:00:00Z",
      detected_at: null,
      uploaded_at: null,
      storage_last_modified: null,
      board_sync_status: null,
      board_sync_time: null,
      board_sync_error: null,
      board_last_synced_review_id: null,
      created_at: "2026-07-10T10:00:00Z",
      updated_at: "2026-07-10T10:00:00Z",
      part: {
        id: 1,
        part_code: "gasket",
        name: "波形垫圈",
        category: "垫圈类",
      },
      device: {
        id: 1,
        device_code: "MP157-VIS-01",
        name: "MP157 主检设备",
      },
      context_explanations: {
        summary: "本记录包含称重、涡流和 F4 流程解释。",
        groups: [
          {
            key: "sensor",
            title: "传感器中文解释",
            summary: "称重通过，LDC 通道 0 未启用。",
            items: [
              {
                source_path: "sensor_context.weighing.raw_adc",
                label: "HX711 原始 ADC",
                value_text: "237171",
                explanation: "HX711 原始 ADC 读数：237171，用于换算重量。",
              },
            ],
          },
        ],
      },
      files: [],
      reviews: [],
    };

    const model = mapDetectionRecordDetailDto(dto);

    expect(model.contextExplanations?.summary).toBe("本记录包含称重、涡流和 F4 流程解释。");
    expect(model.contextExplanations?.groups[0]?.items[0]?.sourcePath).toBe(
      "sensor_context.weighing.raw_adc",
    );
    expect(model.contextExplanations?.groups[0]?.items[0]?.explanation).toContain(
      "HX711 原始 ADC 读数",
    );
  });
});
