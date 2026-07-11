"""MP157 上下文字段中文解释服务测试。"""

from __future__ import annotations

import unittest

from src.services.context_explanation_service import build_context_explanations


class ContextExplanationServiceTestCase(unittest.TestCase):
    """验证云端能把 MP157 上传的工程字段解释成中文业务含义。"""

    def test_explains_mp157_weighing_ldc_f4_and_vision_contexts(self) -> None:
        """称重、涡流、F4 流程和视觉模型字段都应输出普通人能读懂的解释。"""

        result = build_context_explanations(
            vision_context={
                "unet": {"defect_pixels": 0},
                "mobilenetv3_small": {"class_label": "gasket_bad", "confidence": 0.91},
            },
            sensor_context={
                "weighing": {
                    "stable": True,
                    "decision": "pass",
                    "raw_adc": 237171,
                    "net_weight_g": 12.35,
                },
                "ldc1614_eddy_current": {
                    "overall_decision": "fail",
                    "channels": [
                        {"channel": 0, "enabled": False},
                        {"channel": 1, "enabled": True, "raw_code": 9988, "decision": "fail"},
                    ],
                },
                "f4_flow": {
                    "model_ready_ack": True,
                    "active_frame_timeout_ms": 600,
                    "next_step": "upload_then_final_sort",
                },
            },
            decision_context={"result": "bad", "need_ai_review": True},
            device_context={"device_code": "MP157-VIS-01"},
        )

        flat_text = "\n".join(
            item.explanation
            for group in result.groups
            for item in group.items
        )

        self.assertIn("HX711 原始 ADC 读数：237171", flat_text)
        self.assertIn("称重结论：通过", flat_text)
        self.assertIn("LDC1614 通道 0：未启用", flat_text)
        self.assertIn("下一步：先上传云端，上传完成后再通知 F4 做最终分拣", flat_text)
        self.assertIn("UNet 检出缺陷像素数：0", flat_text)
        self.assertTrue(result.summary)

    def test_preserves_unmodeled_nested_fields_as_debug_explanations(self) -> None:
        """已识别模块里的新增字段也不能丢，应至少显示中文兜底解释。"""

        result = build_context_explanations(
            vision_context=None,
            sensor_context={
                "weighing": {
                    "cycle_id": "W-20260710-0001",
                    "raw_adc": 237171,
                },
                "f4_flow": {
                    "job_id": "F4-JOB-001",
                    "next_step": "upload_then_final_sort",
                },
            },
            decision_context=None,
            device_context=None,
        )
        source_paths = [
            item.source_path
            for group in result.groups
            for item in group.items
        ]
        flat_text = "\n".join(
            item.explanation
            for group in result.groups
            for item in group.items
        )

        self.assertIn("sensor_context.weighing.cycle_id", source_paths)
        self.assertIn("sensor_context.f4_flow.job_id", source_paths)
        self.assertIn("原始字段 weighing.cycle_id", flat_text)
        self.assertIn("原始字段 f4_flow.job_id", flat_text)


if __name__ == "__main__":
    unittest.main()
