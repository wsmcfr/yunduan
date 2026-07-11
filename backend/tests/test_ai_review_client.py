"""AI 对话占位客户端测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.core.errors import IntegrationError
from src.integrations.ai_review_client import AIReviewClient


class StubAIReviewClient(AIReviewClient):
    """通过覆写网络层方法，验证协议适配结果而不发真实请求。"""

    def __init__(self) -> None:
        """初始化可观测的桩客户端。"""

        super().__init__()
        self.captured_url: str | None = None
        self.captured_headers: dict[str, str] | None = None
        self.captured_payload: dict | None = None
        self.next_response: dict = {}

    def _fetch_image_asset(self, *, file_object: dict) -> dict | None:  # type: ignore[override]
        """直接返回固定图片内容，避免测试阶段依赖真实网络与 COS。"""

        return {
            "mime_type": "image/png",
            "data_base64": "ZmFrZS1pbWFnZS1ieXRlcw==",
            "data_url": "data:image/png;base64,ZmFrZS1pbWFnZS1ieXRlcw==",
            "image_url": "https://example.com/fake-ai-review-image.png",
            "object_key": str(file_object.get("object_key") or ""),
            "file_kind": str(file_object.get("file_kind") or ""),
        }

    def _post_json(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:  # type: ignore[override]
        """记录请求细节并返回预设响应。"""

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        return self.next_response

    def _post_stream_events(  # type: ignore[override]
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict,
    ):
        """默认把非流式桩响应包装成一条 `__json__` 事件。

        这样 Anthropic Messages 即使改成统一走 SSE/JSON 兼容入口，
        现有测试也仍然可以复用同一套 `next_response` 断言。
        """

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        yield "__json__", self.next_response


class ImageRejectingStubAIReviewClient(StubAIReviewClient):
    """模拟供应商拒绝图片消息块，再验证客户端是否自动退回纯文本重试。"""

    def __init__(self) -> None:
        """初始化可统计多次请求的桩客户端。"""

        super().__init__()
        self.captured_payloads: list[dict] = []

    def _post_json(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:  # type: ignore[override]
        """首次遇到图片输入时抛出供应商错误，后续纯文本请求返回成功。"""

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        self.captured_payloads.append(payload)

        serialized_payload = str(payload)
        if "image_url" in serialized_payload or "input_image" in serialized_payload:
            raise IntegrationError(
                code="ai_provider_http_error",
                message="AI 供应商调用失败，HTTP 400。",
                details={
                    "status_code": 400,
                    "endpoint": url,
                    "response": (
                        "Failed to deserialize the JSON body into the target type messages[2]: "
                        "unknown variant `image_url`, expected `text` at line 1 column 123"
                    ),
                },
            )

        return self.next_response


class StreamingStubAIReviewClient(StubAIReviewClient):
    """通过覆写流式网络层方法，验证 SSE 与兼容回退逻辑。"""

    def __init__(self) -> None:
        """初始化可观测的流式桩客户端。"""

        super().__init__()
        self.stream_events: list[tuple[str | None, dict]] = []

    def _post_stream_events(  # type: ignore[override]
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict,
    ):
        """记录流式请求细节并返回预设事件序列。"""

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        for event in self.stream_events:
            yield event


class FakeCosClient:
    """为真实图片资产构造函数提供固定 COS 下载响应。"""

    def __init__(self) -> None:
        """初始化固定访问地址，便于测试断言图片 URL 透传。"""

        self.access_url = "https://demo-bucket.cos.ap-guangzhou.myqcloud.com/demo/source.png?sign=fake"

    def read_file_bytes(
        self,
        *,
        bucket_name: str,
        region: str,
        object_key: str,
        timeout_seconds: int,
        max_bytes: int,
    ) -> dict:
        """返回一份最小图片字节响应，避免测试依赖真实 COS 网络。"""

        return {
            "access_url": self.access_url,
            "content_type": "image/png",
            "data": b"fake-image-bytes",
        }


class InvalidJsonFallbackStubAIReviewClient(StubAIReviewClient):
    """模拟 OpenClaudeCode `/responses` 返回非 JSON，再验证客户端是否回退。"""

    def __init__(self) -> None:
        """初始化可观察的回退请求上下文。"""

        super().__init__()
        self.captured_urls: list[str] = []
        self.captured_payloads: list[dict] = []

    def _post_json(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:  # type: ignore[override]
        """首次命中 `/responses` 时抛出非 JSON 错误，回退请求则返回成功。"""

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        self.captured_urls.append(url)
        self.captured_payloads.append(payload)

        if url.endswith("/responses"):
            raise IntegrationError(
                code="ai_provider_invalid_json",
                message="AI 供应商返回了无法解析的响应内容。",
                details={
                    "endpoint": url,
                    "response": "<html>proxy mismatch</html>",
                },
            )

        return self.next_response


class InvalidJsonStreamingFallbackStubAIReviewClient(StreamingStubAIReviewClient):
    """模拟 OpenClaudeCode 流式 `/responses` 返回非 JSON，再验证客户端是否回退。"""

    def __init__(self) -> None:
        """初始化流式回退桩客户端。"""

        super().__init__()
        self.captured_urls: list[str] = []
        self.stream_event_map: dict[str, list[tuple[str | None, dict]]] = {}

    def _post_stream_events(  # type: ignore[override]
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict,
    ):
        """按不同端点返回不同事件，便于验证回退是否真的改走了兼容协议。"""

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        self.captured_urls.append(url)

        if url.endswith("/responses"):
            raise IntegrationError(
                code="ai_provider_invalid_json",
                message="AI 供应商返回了无法解析的流式响应内容。",
                details={
                    "endpoint": url,
                    "response": "<html>proxy mismatch</html>",
                },
            )

        for event in self.stream_event_map.get(url, []):
            yield event


class ImageGateway502StubAIReviewClient(StubAIReviewClient):
    """模拟米醋 Responses 在带图片输入时返回 Cloudflare 502。"""

    def __init__(self) -> None:
        """初始化可记录多次请求体的 502 桩客户端。"""

        super().__init__()
        self.captured_urls: list[str] = []
        self.captured_payloads: list[dict] = []

    def _post_json(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:  # type: ignore[override]
        """首次带图片请求抛 502，第二次纯文本 Responses 请求返回成功。"""

        self.captured_url = url
        self.captured_headers = headers
        self.captured_payload = payload
        self.captured_urls.append(url)
        self.captured_payloads.append(payload)

        serialized_payload = str(payload)
        if "input_image" in serialized_payload:
            raise IntegrationError(
                code="ai_provider_http_error",
                message="AI 供应商调用失败，HTTP 502。",
                details={
                    "status_code": 502,
                    "endpoint": url,
                    "response": "Cloudflare bad gateway while forwarding image request",
                },
            )

        return self.next_response


class AIReviewClientTestCase(unittest.TestCase):
    """验证 AI 对话占位客户端会把当前记录上下文带入回答。"""

    def setUp(self) -> None:
        """为每个测试创建新的客户端实例与样例上下文。"""

        self.client = AIReviewClient()
        self.context = {
            "record_id": 1,
            "record_no": "REC-20260420-0001",
            "part_name": "金属垫片样件",
            "part_code": "PART-METAL-01",
            "device_name": "主视觉节点",
            "device_code": "MP157-VIS-01",
            "result": "uncertain",
            "effective_result": "good",
            "review_status": "reviewed",
            "defect_type": "表面划痕",
            "defect_desc": "边缘出现细小划痕，需要人工复核是否属于误检。",
            "confidence_score": 0.62,
            "captured_at": datetime(2026, 4, 20, 2, 1, 21, tzinfo=timezone.utc),
            "detected_at": datetime(2026, 4, 20, 2, 1, 22, tzinfo=timezone.utc),
            "uploaded_at": datetime(2026, 4, 20, 2, 1, 25, tzinfo=timezone.utc),
            "storage_last_modified": None,
            "file_count": 2,
            "review_count": 1,
            "available_file_kinds": ["annotated", "source"],
            "latest_review_decision": "good",
            "latest_review_comment": "人工确认属于误检，可按良品归档。",
            "latest_reviewed_at": datetime(2026, 4, 20, 3, 0, 0, tzinfo=timezone.utc),
        }
        self.referenced_files = [
            {
                "id": 11,
                "file_kind": "annotated",
                "bucket_name": "demo-bucket-1250000000",
                "region": "ap-guangzhou",
                "object_key": "detections/demo/annotated/result.png",
                "uploaded_at": datetime(2026, 4, 20, 2, 1, 25, tzinfo=timezone.utc),
                "preview_url": "https://demo-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/detections/demo/annotated/result.png",
                "analysis_purpose": "MobileNetV3-Small 分类结果图，用于核对 good/bad 标签。",
            },
            {
                "id": 12,
                "file_kind": "source",
                "bucket_name": "demo-bucket-1250000000",
                "region": "ap-guangzhou",
                "object_key": "detections/demo/source/raw.png",
                "uploaded_at": datetime(2026, 4, 20, 2, 1, 24, tzinfo=timezone.utc),
                "preview_url": "https://demo-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/detections/demo/source/raw.png",
                "analysis_purpose": "原始采集图，用于观察零件真实外观。",
            },
        ]

    def test_fetch_image_asset_keeps_provider_access_url_for_openai_image_inputs(self) -> None:
        """验证图片资产会保留 COS 访问 URL，供 OpenAI 类协议引用。"""

        fake_cos_client = FakeCosClient()
        client = AIReviewClient()
        client.cos_client = fake_cos_client  # type: ignore[assignment]

        image_asset = client._fetch_image_asset(
            file_object={
                "bucket_name": "demo-bucket",
                "region": "ap-guangzhou",
                "object_key": "demo/source.png",
                "file_kind": "source",
            }
        )

        self.assertIsNotNone(image_asset)
        self.assertEqual(image_asset["image_url"], fake_cos_client.access_url)  # type: ignore[index]
        self.assertEqual(image_asset["mime_type"], "image/png")  # type: ignore[index]
        self.assertTrue(image_asset["data_url"].startswith("data:image/png;base64,"))  # type: ignore[index]

    def test_chat_about_record_mentions_current_record_context(self) -> None:
        """验证回答会明确引用当前记录、结果和图像对象上下文。"""

        response = self.client.chat_about_record(
            record_id=1,
            provider_hint="context-chat",
            question="结合当前图片和检测结果，告诉我这条记录为什么建议人工复核？",
            history=[],
            context=self.context,
            referenced_files=self.referenced_files,
        )

        self.assertEqual(response["status"], "contextual_response")
        self.assertEqual(response["record_id"], 1)
        self.assertIn("REC-20260420-0001", response["answer"])
        self.assertIn("MP 初检结果为 uncertain", response["answer"])
        self.assertIn("annotated:detections/demo/annotated/result.png", response["answer"])
        self.assertGreaterEqual(len(response["suggested_questions"]), 3)

    def test_chat_about_record_mentions_history_when_multi_turn(self) -> None:
        """验证多轮对话时回答会提示已经保留上一轮追问上下文。"""

        response = self.client.chat_about_record(
            record_id=1,
            provider_hint="context-chat",
            question="继续解释这条记录的时间链路。",
            history=[
                {"role": "user", "content": "先帮我总结风险点"},
                {"role": "assistant", "content": "这条记录需要重点关注边缘划痕是否为误检。"},
            ],
            context=self.context,
            referenced_files=self.referenced_files,
        )

        self.assertIn("时间链路", response["answer"])
        self.assertIn("已保留你当前会话中的追问上下文", response["answer"])

    def test_prompt_contract_explicitly_limits_analysis_to_single_side_images(self) -> None:
        """验证系统提示词会明确声明当前业务默认只分析单面图像。"""

        instruction = self.client._build_system_instruction(  # type: ignore[attr-defined]
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "gateway_name": "OpenClaudeCode",
            },
            has_loaded_images=True,
            task_mode="chat",
        )

        self.assertIn("当前业务默认只检测零件的单面图像", instruction)
        self.assertIn("不要要求补拍另一面", instruction)
        self.assertIn("一线质检员和普通管理人员", instruction)

    def test_review_prompt_requires_same_side_recheck_instead_of_other_side_images(self) -> None:
        """验证 AI 复核提示词会把补充建议限制在当前这一面。"""

        prompt = self.client._build_review_user_prompt(  # type: ignore[attr-defined]
            note="请给出人工复核建议。",
            context=self.context,
            referenced_files=self.referenced_files,
            image_assets=[{"object_key": "detections/demo/source/raw.png"}],
        )

        self.assertIn("当前业务默认只检测单面图像", prompt)
        self.assertIn("不要建议补拍另一面", prompt)
        self.assertIn("重点看哪里", prompt)

    def test_review_prompt_requires_board_correction_fields_when_result_conflicts(self) -> None:
        """验证 AI 复核摘要提示词也会要求输出板端修正弹窗字段。"""

        prompt = self.client._build_review_user_prompt(  # type: ignore[attr-defined]
            note="如果 AI 判断和板端初检不一致，请告诉我修正弹窗怎么填。",
            context={**self.context, "result": "good", "effective_result": "good", "review_status": "pending"},
            referenced_files=self.referenced_files,
            image_assets=[{"object_key": "detections/demo/source/raw.png"}],
        )

        self.assertIn("修正板端结果填写建议", prompt)
        self.assertIn("decision 填 bad", prompt)
        self.assertIn("decision 填 good", prompt)
        self.assertIn("cloud_reason 填一句可直接复制到修正原因框的中文说明", prompt)

    def test_chat_prompt_explains_model_artifacts_and_requires_direct_good_bad_advice(self) -> None:
        """验证对话提示词会解释模型产物图，并要求直接给出良品/不良建议。"""

        prompt = self.client._build_chat_user_prompt(  # type: ignore[attr-defined]
            question="结合这四张图给我分析这个到底是好的还是坏的？",
            context={**self.context, "review_status": "pending", "review_count": 0},
            referenced_files=[
                {
                    **self.referenced_files[0],
                    "object_key": "detections/demo/annotated/segment_mask.png",
                    "analysis_purpose": "UNet 分割 mask：只显示模型认为疑似缺陷的像素区域。",
                },
                {
                    **self.referenced_files[0],
                    "object_key": "detections/demo/annotated/segment_overlay.jpg",
                    "analysis_purpose": "UNet 分割叠加图：把缺陷区域覆盖到原始图上。",
                },
                {
                    **self.referenced_files[0],
                    "object_key": "detections/demo/annotated/classification_gasket_good.jpg",
                    "analysis_purpose": "MobileNetV3-Small 分类结果图：用于核对 good/bad 分类标签。",
                },
                {
                    **self.referenced_files[1],
                    "object_key": "detections/demo/source/segment_raw.jpg",
                    "analysis_purpose": "原始采集图：用于观察真实外观。",
                },
            ],
            image_assets=[
                {"object_key": "segment_mask.png"},
                {"object_key": "segment_overlay.jpg"},
                {"object_key": "classification_gasket_good.jpg"},
                {"object_key": "segment_raw.jpg"},
            ],
        )

        self.assertIn("UNet 分割 mask", prompt)
        self.assertIn("UNet 分割叠加图", prompt)
        self.assertIn("MobileNetV3-Small 分类结果图", prompt)
        self.assertIn("原始采集图", prompt)
        self.assertIn("先给出倾向结论", prompt)
        self.assertIn("不能把“尚未人工审核”当成回避判断的理由", prompt)

    def test_chat_prompt_renders_chinese_context_explanations(self) -> None:
        """验证 AI 提示词会把云端转换后的中文上下文解释作为独立段落提供给模型。"""

        prompt = self.client._build_chat_user_prompt(  # type: ignore[attr-defined]
            question="把传感器数据讲成人话。",
            context={
                **self.context,
                "context_explanations": {
                    "summary": "已将 MP157 上报的传感器上下文转换为中文解释。",
                    "groups": [
                        {
                            "key": "sensor",
                            "title": "传感器中文解释",
                            "summary": "称重结论：通过。",
                            "items": [
                                {
                                    "source_path": "sensor_context.weighing.decision",
                                    "label": "称重结论",
                                    "value_text": "pass",
                                    "explanation": "称重结论：通过，重量传感器认为该样本在允许范围内。",
                                }
                            ],
                        }
                    ],
                },
            },
            referenced_files=self.referenced_files,
            image_assets=[{"object_key": "detections/demo/source/raw.png"}],
        )

        self.assertIn("中文上下文解释", prompt)
        self.assertIn("称重结论：通过", prompt)

    def test_chat_prompt_requires_board_correction_fields_when_ai_advice_conflicts_with_mp157_result(self) -> None:
        """验证 AI 倾向与 MP157 初检冲突时，提示词要求给出板端修正弹窗填写建议。"""

        prompt_for_good_board_result = self.client._build_chat_user_prompt(  # type: ignore[attr-defined]
            question="请判断这条样件质量并给现场处理建议。",
            context={
                **self.context,
                "result": "good",
                "effective_result": "good",
                "review_status": "pending",
                "review_count": 0,
                "defect_type": "划痕",
            },
            referenced_files=self.referenced_files,
            image_assets=[{"object_key": "detections/demo/source/raw.png"}],
        )
        prompt_for_bad_board_result = self.client._build_chat_user_prompt(  # type: ignore[attr-defined]
            question="请判断这条样件质量并给现场处理建议。",
            context={
                **self.context,
                "result": "bad",
                "effective_result": "bad",
                "review_status": "pending",
                "review_count": 0,
                "defect_type": "划痕",
            },
            referenced_files=self.referenced_files,
            image_assets=[{"object_key": "detections/demo/source/raw.png"}],
        )

        self.assertIn("修正板端结果填写建议", prompt_for_good_board_result)
        self.assertIn("MP157 初检结果（record_context.result）为 good", prompt_for_good_board_result)
        self.assertIn("decision 填 bad", prompt_for_good_board_result)
        self.assertIn("defect_type 填你判断出的缺陷类型", prompt_for_good_board_result)
        self.assertIn("cloud_reason 填一句可直接复制到修正原因框的中文说明", prompt_for_good_board_result)
        self.assertIn("decision 填 good", prompt_for_bad_board_result)
        self.assertIn("defect_type 填 null 或“无明显缺陷”", prompt_for_bad_board_result)
        self.assertIn("云端复核认为当前证据更支持良品", prompt_for_bad_board_result)

    def test_chat_request_embeds_previous_turns_in_current_user_prompt_for_followups(self) -> None:
        """验证后续追问的当前提示词会显式携带上一轮问答，避免模型丢失上下文。"""

        client = StubAIReviewClient()
        client.next_response = {
            "choices": [
                {
                    "message": {
                        "content": "这次回答已经承接上一轮上下文。",
                    }
                }
            ]
        }

        client.chat_about_record(
            record_id=1,
            provider_hint="DeepSeek 官方",
            question="那这个位置为什么算风险？",
            history=[
                {"role": "user", "content": "先判断它到底是好的还是坏的。"},
                {"role": "assistant", "content": "更倾向坏品，主要风险在内孔边缘疑似划痕。"},
            ],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "DeepSeek Chat",
                "model_identifier": "deepseek-chat",
                "protocol_type": "openai_compatible",
                "auth_mode": "authorization_bearer",
                "base_url": "https://api.deepseek.com",
                "user_agent": None,
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "DeepSeek 官方",
                "gateway_vendor": "deepseek",
                "api_key": "deepseek-secret-key",
            },
        )

        current_user_content = client.captured_payload["messages"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("同一弹窗历史对话", current_user_content)
        self.assertIn("先判断它到底是好的还是坏的", current_user_content)
        self.assertIn("更倾向坏品，主要风险在内孔边缘疑似划痕", current_user_content)
        self.assertIn("必须承接这些历史理解用户追问里的指代", current_user_content)
        self.assertTrue(current_user_content.startswith("请基于下面这条检测记录进行分析"))
        self.assertEqual(
            client.captured_payload["messages"][-1]["content"][1]["image_url"]["url"],  # type: ignore[index]
            "https://example.com/fake-ai-review-image.png",
        )
        self.assertNotIn(
            "data:image/png;base64",
            client.captured_payload["messages"][-1]["content"][1]["image_url"]["url"],  # type: ignore[index]
        )

    def test_short_confirmation_followup_executes_previous_assistant_offer(self) -> None:
        """验证“可以”这类短确认会承接上一轮助手提出的待执行动作。"""

        client = StubAIReviewClient()
        client.next_response = {
            "choices": [
                {
                    "message": {
                        "content": "已直接写出复核备注。",
                    }
                }
            ]
        }

        client.chat_about_record(
            record_id=1,
            provider_hint="DeepSeek 官方",
            question="可以",
            history=[
                {"role": "user", "content": "给我说明这个是好的还是坏的。"},
                {
                    "role": "assistant",
                    "content": (
                        "如果你要，我下一步可以直接帮你写一条可复制到复核备注里的中文判定说明。"
                    ),
                },
            ],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "DeepSeek Chat",
                "model_identifier": "deepseek-chat",
                "protocol_type": "openai_compatible",
                "auth_mode": "authorization_bearer",
                "base_url": "https://api.deepseek.com",
                "user_agent": None,
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "DeepSeek 官方",
                "gateway_vendor": "deepseek",
                "api_key": "deepseek-secret-key",
            },
        )

        current_user_content = client.captured_payload["messages"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("当前用户只回复了短确认词“可以”", current_user_content)
        self.assertIn("直接生成对应内容，不要重新从头判断良品或坏品", current_user_content)
        self.assertIn("可复制到复核备注里的中文判定说明", current_user_content)

    def test_chat_about_record_builds_openai_responses_request_for_codex(self) -> None:
        """验证 Codex / OpenAI Responses 模式会带上 Bearer、UA 和图片输入。"""

        client = StubAIReviewClient()
        client.next_response = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "这是来自 Codex 协议的真实回答。",
                        }
                    ],
                }
            ]
        }

        response = client.chat_about_record(
            record_id=1,
            provider_hint="OpenClaudeCode / Codex",
            question="结合图像说明为什么这条记录要复核。",
            history=[
                {"role": "assistant", "content": "这是前端打开弹窗时的引导语。"},
                {"role": "user", "content": "结合图像说明为什么这条记录要复核。"},
            ],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai/v1",
                "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "api_key": "sk-demo-codex",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["answer"], "这是来自 Codex 协议的真实回答。")
        self.assertEqual(client.captured_url, "https://www.micuapi.ai/v1/responses")
        self.assertEqual(
            client.captured_headers["Authorization"],  # type: ignore[index]
            "Bearer sk-demo-codex",
        )
        self.assertIn("codex_cli_rs", client.captured_headers["User-Agent"])  # type: ignore[index]
        self.assertEqual(client.captured_payload["model"], "gpt-5.4")  # type: ignore[index]
        self.assertEqual(len(client.captured_payload["input"]), 1)  # type: ignore[index]
        self.assertNotIn("这是前端打开弹窗时的引导语", str(client.captured_payload))
        self.assertEqual(
            client.captured_payload["input"][-1]["content"][1]["type"],  # type: ignore[index]
            "input_image",
        )
        self.assertEqual(
            client.captured_payload["input"][-1]["content"][1]["image_url"],  # type: ignore[index]
            "https://example.com/fake-ai-review-image.png",
        )
        self.assertNotIn(
            "data:image/png;base64",
            client.captured_payload["input"][-1]["content"][1]["image_url"],  # type: ignore[index]
        )

    def test_openai_responses_does_not_answer_without_images_when_image_request_gets_502(self) -> None:
        """验证米醋 Responses 首轮带图失败时，不能无图兜底返回质检结论。"""

        client = ImageGateway502StubAIReviewClient()

        with self.assertRaises(IntegrationError):
            client.chat_about_record(
                record_id=1,
                provider_hint="OpenClaudeCode / Codex",
                question="这个是好的还是坏的？",
                history=[],
                context=self.context,
                referenced_files=self.referenced_files,
                model_context={
                    "display_name": "OpenClaudeCode Codex",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
            )

        self.assertEqual(client.captured_urls, ["https://www.micuapi.ai/v1/responses"])
        self.assertIn("input_image", str(client.captured_payloads[0]))

    def test_openclaudecode_responses_vision_uses_compact_prompt_to_avoid_gateway_502(self) -> None:
        """验证米醋 Responses 追问压缩历史、默认不重发图片，但保留图片读取位置。"""

        client = StubAIReviewClient()
        client.next_response = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "压缩提示词下的回答。"}],
                }
            ]
        }
        long_context = {
            **self.context,
            "vision_context": {
                "very_long_debug_blob": "视觉链路调试字段" * 400,
            },
            "device_context": {
                "very_long_device_blob": "设备上下文字段" * 400,
            },
        }

        client.chat_about_record(
            record_id=1,
            provider_hint="OpenClaudeCode / Codex",
            question="这个是好的还是坏的？",
            history=[
                {"role": "user", "content": "上一轮很长的问题" * 80},
                {"role": "assistant", "content": "上一轮很长的回答" * 80},
            ],
            context=long_context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai/v1",
                "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-codex",
            },
        )

        current_prompt = client.captured_payload["input"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("紧凑结构化摘要", current_prompt)
        self.assertIn("UNet mask", current_prompt)
        self.assertIn("MobileNetV3-Small", current_prompt)
        self.assertIn("preview_url=", current_prompt)
        self.assertIn("https://demo-bucket-1250000000.cos.ap-guangzhou.myqcloud.com", current_prompt)
        self.assertNotIn("very_long_debug_blob", current_prompt)
        self.assertLess(len(current_prompt), 5200)
        self.assertNotIn("input_image", str(client.captured_payload))

    def test_openclaudecode_responses_first_turn_still_sends_images(self) -> None:
        """验证首轮视觉判断仍会发送图片，让模型先建立当前记录的视觉依据。"""

        client = StubAIReviewClient()
        client.next_response = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "首轮已结合图片判断。"}],
                }
            ]
        }

        client.chat_about_record(
            record_id=1,
            provider_hint="OpenClaudeCode / Codex",
            question="这个是好的还是坏的？",
            history=[],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai/v1",
                "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-codex",
            },
        )

        self.assertIn("input_image", str(client.captured_payload))
        current_prompt = client.captured_payload["input"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("本轮实际附带图片数量：2", current_prompt)

    def test_openclaudecode_responses_first_user_turn_ignores_ui_opening_message(self) -> None:
        """验证前端弹窗开场白不会被当成真实多轮历史发给米醋。"""

        client = StubAIReviewClient()
        client.next_response = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "首个用户问题已结合图片判断。"}],
                }
            ]
        }

        client.chat_about_record(
            record_id=1,
            provider_hint="OpenClaudeCode / Codex",
            question="给我说明这个是好的还是坏的",
            history=[
                {
                    "role": "assistant",
                    "content": (
                        "已进入记录 MP157-20260520-205037 的 AI 对话模式。\n"
                        "当前零件为 波形垫圈（gasket），设备为 MP157_test。"
                    ),
                }
            ],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai/v1",
                "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-codex",
            },
        )

        self.assertIn("input_image", str(client.captured_payload))
        self.assertNotIn("已进入记录", str(client.captured_payload))
        self.assertEqual(len(client.captured_payload["input"]), 1)  # type: ignore[arg-type,index]
        current_prompt = client.captured_payload["input"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("本轮实际附带图片数量：2", current_prompt)

    def test_openclaudecode_responses_followup_resends_images_when_user_explicitly_asks(self) -> None:
        """验证用户明确要求重新看图时，即使有上一轮响应 ID，也会重新附带图片。"""

        client = StubAIReviewClient()
        client.next_response = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "已按图片重新判断。"}],
                }
            ]
        }

        client.chat_about_record(
            record_id=1,
            provider_hint="OpenClaudeCode / Codex",
            question="请重新看图判断这个到底是不是坏品。",
            history=[
                {"role": "user", "content": "这个是好的还是坏的？"},
                {"role": "assistant", "content": "更像良品，但板端初检为 bad。"},
            ],
            context=self.context,
            referenced_files=self.referenced_files,
            previous_response_id="resp_previous_context",
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai/v1",
                "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-codex",
            },
        )

        self.assertIn("input_image", str(client.captured_payload))
        current_prompt = client.captured_payload["input"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("压缩后的同一弹窗历史", current_prompt)

    def test_openclaudecode_responses_followup_uses_local_history_without_previous_response_id(self) -> None:
        """验证米醋 Responses 追问按 CLI/opencode 策略使用本地历史，不发送 previous_response_id。"""

        client = StubAIReviewClient()
        client.next_response = {
            "id": "resp_next_context",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "已承接上一轮上下文。"}],
                }
            ],
        }

        response = client.chat_about_record(
            record_id=1,
            provider_hint="OpenClaudeCode / Codex",
            question="继续解释刚才说的位置。",
            history=[
                {"role": "user", "content": "这个是好的还是坏的？"},
                {"role": "assistant", "content": "更像不良，重点看上方环形表面。"},
            ],
            context=self.context,
            referenced_files=self.referenced_files,
            previous_response_id="resp_previous_context",
            model_context={
                "display_name": "OpenClaudeCode Codex",
                "model_identifier": "gpt-5.4",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai/v1",
                "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-codex",
            },
        )

        self.assertEqual(response["provider_response_id"], "resp_next_context")
        self.assertNotIn("previous_response_id", client.captured_payload)  # type: ignore[operator]
        self.assertTrue(client.captured_payload["store"])  # type: ignore[index]
        self.assertEqual(len(client.captured_payload["input"]), 1)  # type: ignore[arg-type]
        self.assertEqual(client.captured_payload["input"][0]["role"], "user")  # type: ignore[index]
        self.assertNotIn("input_image", str(client.captured_payload))
        current_prompt = client.captured_payload["input"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("压缩后的同一弹窗历史", current_prompt)
        self.assertIn("更像不良，重点看上方环形表面", current_prompt)
        self.assertIn("preview_url=", current_prompt)
        self.assertIn("detections/demo/source/raw.png", current_prompt)

    def test_openclaudecode_stream_metadata_uses_http_responses_with_local_history(self) -> None:
        """验证米醋记录页 metadata 链路使用真流式请求，并继续依靠本地历史承接上下文。"""

        client = StubAIReviewClient()
        client.next_response = {
            "id": "resp_stream_next",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "已用压缩历史承接上下文。"}],
                }
            ],
        }

        items = list(
            client.request_openai_responses_stream_metadata(
                model_context={
                    "display_name": "OpenClaudeCode Codex",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
                system_instruction="系统提示",
                history=[
                    {"role": "user", "content": "这个是好的还是坏的？"},
                    {"role": "assistant", "content": "更像良品，需要把板端 bad 修正为 good。"},
                ],
                user_prompt="压缩后的同一弹窗历史：更像良品，需要把板端 bad 修正为 good",
                image_assets=[],
                previous_response_id="resp_previous_context",
            )
        )

        self.assertEqual(client.captured_url, "https://www.micuapi.ai/v1/responses")
        self.assertTrue(client.captured_payload["stream"])  # type: ignore[index]
        self.assertNotIn("previous_response_id", client.captured_payload)  # type: ignore[operator]
        self.assertEqual(len(client.captured_payload["input"]), 1)  # type: ignore[arg-type]
        self.assertEqual(client.captured_payload["input"][0]["role"], "user")  # type: ignore[index]
        self.assertNotIn("input_image", str(client.captured_payload))
        self.assertEqual(items[0], {"type": "metadata", "provider_response_id": "resp_stream_next"})
        self.assertEqual("".join(str(item.get("text") or "") for item in items), "已用压缩历史承接上下文。")

    def test_openclaudecode_streaming_responses_metadata_returns_http_response_id(self) -> None:
        """验证记录页真流式 meta/done 链路可以拿到 HTTP Responses 返回的响应 ID。"""

        client = StubAIReviewClient()
        client.next_response = {
            "id": "resp_first_http",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "首轮回答。"}],
                }
            ],
        }

        items = list(
            client.request_openai_responses_stream_metadata(
                model_context={
                    "display_name": "OpenClaudeCode Codex",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
                system_instruction="系统提示",
                history=[],
                user_prompt="用户问题",
                image_assets=[{"image_url": "https://example.com/image.png", "data_url": "data:image/png;base64,AA=="}],
            )
        )

        self.assertEqual(items[0], {"type": "metadata", "provider_response_id": "resp_first_http"})
        self.assertEqual("".join(str(item.get("text") or "") for item in items), "首轮回答。")
        self.assertTrue(client.captured_payload["stream"])  # type: ignore[index]
        self.assertIn("input_image", str(client.captured_payload))

    def test_openclaudecode_streaming_responses_metadata_emits_deltas_before_completed_metadata(self) -> None:
        """验证米醋记录页 metadata 链路会透传上游 delta，而不是等整段响应后再切片。"""

        client = StreamingStubAIReviewClient()
        client.stream_events = [
            (None, {"type": "response.output_text.delta", "delta": "第一段"}),
            (None, {"type": "response.output_text.delta", "delta": "第二段"}),
            (
                None,
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_stream_done",
                        "output": [
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "第一段第二段"}],
                            }
                        ],
                    },
                },
            ),
        ]

        items = list(
            client.request_openai_responses_stream_metadata(
                model_context={
                    "display_name": "OpenClaudeCode Codex",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0",
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
                system_instruction="系统提示",
                history=[],
                user_prompt="用户问题",
                image_assets=[],
            )
        )

        self.assertEqual(
            items,
            [
                {"type": "delta", "text": "第一段"},
                {"type": "delta", "text": "第二段"},
                {"type": "metadata", "provider_response_id": "resp_stream_done"},
            ],
        )
        self.assertTrue(client.captured_payload["stream"])  # type: ignore[index]

    def test_chat_about_record_builds_anthropic_messages_request_for_claude(self) -> None:
        """验证 Claude / Anthropic Messages 模式会带上 x-api-key 与 anthropic-version。"""

        client = StubAIReviewClient()
        client.next_response = {
            "content": [
                {
                    "type": "text",
                    "text": "这是来自 Claude 协议的真实回答。",
                }
            ]
        }

        response = client.chat_about_record(
            record_id=1,
            provider_hint="Claude 官方",
            question="帮我总结这条记录的复核建议。",
            history=[],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "Claude 官方",
                "model_identifier": "claude-sonnet-4-5",
                "protocol_type": "anthropic_messages",
                "auth_mode": "x_api_key",
                "base_url": "https://api.anthropic.com",
                "user_agent": None,
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "Claude 官方",
                "api_key": "claude-secret-key",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["answer"], "这是来自 Claude 协议的真实回答。")
        self.assertEqual(client.captured_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(client.captured_headers["x-api-key"], "claude-secret-key")  # type: ignore[index]
        self.assertEqual(client.captured_headers["anthropic-version"], "2023-06-01")  # type: ignore[index]
        self.assertEqual(client.captured_payload["model"], "claude-sonnet-4-5")  # type: ignore[index]
        self.assertEqual(
            client.captured_payload["messages"][-1]["content"][1]["type"],  # type: ignore[index]
            "image",
        )

    def test_chat_about_record_keeps_selected_responses_protocol_when_provider_returns_invalid_json(self) -> None:
        """验证选中 OpenAI Responses 时，即使供应商失败也不能回退到 Chat Completions。

        设置页里模型协议已经明确为 OpenAI Responses，调用层必须严格尊重这个选择。
        如果这里自动改走 `/chat/completions`，供应商调用记录会出现和配置不一致的路径，
        现场排查时会误以为模型配置没有生效。
        """

        client = InvalidJsonFallbackStubAIReviewClient()

        with self.assertRaises(IntegrationError):
            client.chat_about_record(
                record_id=1,
                provider_hint="gpt-5.4 / OpenClaudeCode",
                question="请说明为什么统计 AI 会失败。",
                history=[],
                context=self.context,
                referenced_files=self.referenced_files,
                model_context={
                    "display_name": "gpt-5.4",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
            )

        self.assertEqual(client.captured_urls, ["https://www.micuapi.ai/v1/responses"])

    def test_chat_about_record_reads_anthropic_messages_event_stream_for_grok(self) -> None:
        """验证 OpenClaudeCode Grok 即使直接返回 SSE，也能被 Anthropic Messages 兼容层正确拼出答案。"""

        client = StreamingStubAIReviewClient()
        client.stream_events = [
            ("message_start", {"type": "message_start", "message": {"content": []}}),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "这是来自 SSE 的 "},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Grok 回答。"},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]

        response = client.chat_about_record(
            record_id=1,
            provider_hint="grok / OpenClaudeCode",
            question="帮我总结当前记录。",
            history=[],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "OpenClaudeCode Grok",
                "model_identifier": "grok-4.20-fast",
                "protocol_type": "anthropic_messages",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.micuapi.ai",
                "user_agent": "claude-cli/2.0.76 (external, cli)",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "grok",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-grok",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["answer"], "这是来自 SSE 的 Grok 回答。")
        self.assertEqual(client.captured_url, "https://www.micuapi.ai/v1/messages")

    def test_stream_chat_about_record_yields_anthropic_message_deltas(self) -> None:
        """验证 Anthropic Messages 直接返回 SSE 时，流式接口会逐段转发文本。"""

        client = StreamingStubAIReviewClient()
        client.stream_events = [
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "第一段。"},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "第二段。"},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]

        chunks = list(
            client.stream_chat_about_record(
                record_id=1,
                provider_hint="grok / OpenClaudeCode",
                question="继续分析这条记录。",
                history=[],
                context=self.context,
                referenced_files=self.referenced_files,
                model_context={
                    "display_name": "OpenClaudeCode Grok",
                    "model_identifier": "grok-4.20-fast",
                    "protocol_type": "anthropic_messages",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai",
                    "user_agent": "claude-cli/2.0.76 (external, cli)",
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "grok",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-grok",
                },
            )
        )

        self.assertEqual(chunks, ["第一段。", "第二段。"])
        self.assertEqual(client.captured_url, "https://www.micuapi.ai/v1/messages")

    def test_statistics_prompt_uses_text_snapshot_instead_of_raw_json(self) -> None:
        """验证统计页提示词改为文本摘要，避免把整包 JSON 直接塞进 Grok Messages。"""

        prompt = self.client._build_statistics_user_prompt(
            note=None,
            statistics_context={
                "filters": {
                    "start_date": None,
                    "end_date": None,
                    "days": 7,
                    "part_id": None,
                    "device_id": None,
                },
                "summary": {
                    "total_count": 10,
                    "good_count": 8,
                    "bad_count": 1,
                    "uncertain_count": 1,
                    "reviewed_count": 6,
                    "pending_review_count": 4,
                    "pass_rate": 0.8,
                },
                "defect_distribution": [{"defect_type": "毛刺", "count": 1}],
                "sample_gallery": {"groups": [{"part_name": "不应直接原样进提示词"}]},
            },
        )

        self.assertIn("统计报告摘要：", prompt)
        self.assertIn("【汇总指标】", prompt)
        self.assertIn("【缺陷分布", prompt)
        self.assertNotIn("\"sample_gallery\"", prompt)
        self.assertNotIn("{\"filters\"", prompt)

    def test_chat_about_record_retries_without_images_when_provider_rejects_image_blocks(self) -> None:
        """验证文本模型被误标为视觉时，会自动退回纯文本对话。"""

        client = ImageRejectingStubAIReviewClient()
        client.next_response = {
            "choices": [
                {
                    "message": {
                        "content": "供应商拒绝图片后，客户端已自动退回纯文本回答。",
                    }
                }
            ]
        }

        response = client.chat_about_record(
            record_id=1,
            provider_hint="DeepSeek 官方",
            question="结合当前图片说明这条记录是否需要人工复核。",
            history=[],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "DeepSeek Reasoner",
                "model_identifier": "deepseek-reasoner",
                "protocol_type": "openai_compatible",
                "auth_mode": "authorization_bearer",
                "base_url": "https://api.deepseek.com",
                "user_agent": None,
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "DeepSeek 官方",
                "gateway_vendor": "deepseek",
                "api_key": "deepseek-secret-key",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["answer"], "供应商拒绝图片后，客户端已自动退回纯文本回答。")
        self.assertEqual(len(client.captured_payloads), 2)
        self.assertIn("image_url", str(client.captured_payloads[0]))
        self.assertNotIn("image_url", str(client.captured_payloads[1]))

    def test_request_review_retries_without_images_when_provider_rejects_image_blocks(self) -> None:
        """验证 AI 复核摘要同样会在图片被拒绝时自动退回纯文本。"""

        client = ImageRejectingStubAIReviewClient()
        client.next_response = {
            "choices": [
                {
                    "message": {
                        "content": "这是一条已经退回纯文本后的 AI 复核摘要。",
                    }
                }
            ]
        }

        response = client.request_review(
            record_id=1,
            provider_hint="DeepSeek 官方",
            note="优先判断是否需要继续人工复核。",
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "DeepSeek Reasoner",
                "model_identifier": "deepseek-reasoner",
                "protocol_type": "openai_compatible",
                "auth_mode": "authorization_bearer",
                "base_url": "https://api.deepseek.com",
                "user_agent": None,
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "DeepSeek 官方",
                "gateway_vendor": "deepseek",
                "api_key": "deepseek-secret-key",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["message"], "这是一条已经退回纯文本后的 AI 复核摘要。")
        self.assertEqual(len(client.captured_payloads), 2)
        self.assertIn("image_url", str(client.captured_payloads[0]))
        self.assertNotIn("image_url", str(client.captured_payloads[1]))

    def test_stream_chat_about_record_yields_openai_compatible_deltas(self) -> None:
        """验证 Chat Completions 流式模式会按增量片段持续产出文本。"""

        client = StreamingStubAIReviewClient()
        client.stream_events = [
            (
                None,
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "第一段流式内容。",
                            }
                        }
                    ]
                },
            ),
            (
                None,
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "第二段流式内容。",
                            }
                        }
                    ]
                },
            ),
        ]

        output_chunks = list(
            client.stream_chat_about_record(
                record_id=1,
                provider_hint="DeepSeek 官方",
                question="请流式说明这条记录的风险。",
                history=[],
                context=self.context,
                referenced_files=self.referenced_files,
                model_context={
                    "display_name": "DeepSeek Chat",
                    "model_identifier": "deepseek-chat",
                    "protocol_type": "openai_compatible",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://api.deepseek.com",
                    "user_agent": None,
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "DeepSeek 官方",
                    "gateway_vendor": "deepseek",
                    "api_key": "deepseek-secret-key",
                },
            )
        )

        self.assertEqual(output_chunks, ["第一段流式内容。", "第二段流式内容。"])
        self.assertEqual(client.captured_url, "https://api.deepseek.com/chat/completions")
        self.assertTrue(client.captured_payload["stream"])  # type: ignore[index]

    def test_stream_chat_about_record_embeds_previous_turns_in_current_user_prompt(self) -> None:
        """验证流式追问同样会在当前提示词里显式携带历史上下文。"""

        client = StreamingStubAIReviewClient()
        client.stream_events = [
            (
                None,
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "已承接上一轮回答。",
                            }
                        }
                    ]
                },
            )
        ]

        list(
            client.stream_chat_about_record(
                record_id=1,
                provider_hint="DeepSeek 官方",
                question="那为什么还要人工确认？",
                history=[
                    {"role": "user", "content": "先判断这个是好品还是坏品。"},
                    {"role": "assistant", "content": "更倾向坏品，疑似外轮廓有缺口。"},
                ],
                context=self.context,
                referenced_files=self.referenced_files,
                model_context={
                    "display_name": "DeepSeek Chat",
                    "model_identifier": "deepseek-chat",
                    "protocol_type": "openai_compatible",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://api.deepseek.com",
                    "user_agent": None,
                    "supports_vision": True,
                    "supports_stream": True,
                    "gateway_name": "DeepSeek 官方",
                    "gateway_vendor": "deepseek",
                    "api_key": "deepseek-secret-key",
                },
            )
        )

        current_user_content = client.captured_payload["messages"][-1]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("同一弹窗历史对话", current_user_content)
        self.assertIn("更倾向坏品，疑似外轮廓有缺口", current_user_content)
        self.assertIn("用户问题：那为什么还要人工确认？", current_user_content)
        self.assertTrue(current_user_content.startswith("请基于下面这条检测记录进行分析"))

    def test_openclaudecode_statistics_chat_embeds_history_in_current_user_prompt(self) -> None:
        """验证米醋统计追问也用本轮 prompt 承接历史，避免独立 history input 触发 502。"""

        client = StreamingStubAIReviewClient()
        client.stream_events = [
            (
                "__json__",
                {
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "已承接统计追问。"}],
                        }
                    ]
                },
            )
        ]

        output_chunks = list(
            client.stream_statistics_chat(
                provider_hint="OpenClaudeCode / Codex",
                question="那设备 A 要不要优先排查？",
                note="关注坏品集中原因。",
                history=[
                    {"role": "user", "content": "先总结这批数据的主要风险。"},
                    {"role": "assistant", "content": "设备 A 的 bad_count 较高，需要重点关注。"},
                ],
                statistics_context={
                    "summary": {"total_count": 20, "bad_count": 5},
                    "device_ranking": [{"device_name": "设备 A", "bad_count": 4}],
                },
                model_context={
                    "display_name": "OpenClaudeCode Codex",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0",
                    "supports_vision": False,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
            )
        )

        self.assertEqual("".join(output_chunks), "已承接统计追问。")
        self.assertEqual(client.captured_url, "https://www.micuapi.ai/v1/responses")
        self.assertEqual(len(client.captured_payload["input"]), 1)  # type: ignore[arg-type]
        self.assertEqual(client.captured_payload["input"][0]["role"], "user")  # type: ignore[index]
        current_prompt = client.captured_payload["input"][0]["content"][0]["text"]  # type: ignore[index]
        self.assertIn("统计页历史对话", current_prompt)
        self.assertIn("设备 A 的 bad_count 较高", current_prompt)
        self.assertIn("用户问题：那设备 A 要不要优先排查？", current_prompt)

    def test_stream_statistics_analysis_falls_back_when_gateway_returns_full_json(self) -> None:
        """验证流式模式下若兼容网关直接回整包 JSON，客户端仍会退回切片输出。"""

        client = StreamingStubAIReviewClient()
        full_answer = "这是网关直接返回的完整统计分析文本。"
        client.stream_events = [
            (
                "__json__",
                {
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": full_answer,
                                }
                            ],
                        }
                    ]
                },
            )
        ]

        output_chunks = list(
            client.stream_statistics_analysis(
                provider_hint="OpenClaudeCode / Codex",
                note="请流式总结当前批次风险。",
                statistics_context={
                    "summary": {"total_count": 12, "bad_count": 2},
                    "key_findings": ["某零件风险较高"],
                },
                model_context={
                    "display_name": "OpenClaudeCode Codex",
                    "model_identifier": "gpt-5.4",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0",
                    "supports_vision": False,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
            )
        )

        self.assertEqual("".join(output_chunks), full_answer)
        self.assertEqual(client.captured_url, "https://www.micuapi.ai/v1/responses")
        self.assertTrue(client.captured_payload["stream"])  # type: ignore[index]

    def test_stream_statistics_analysis_keeps_selected_responses_protocol_when_provider_returns_invalid_json(self) -> None:
        """验证统计流式分析选中 Responses 时，也不能隐式改走 Chat Completions。"""

        client = InvalidJsonStreamingFallbackStubAIReviewClient()

        with self.assertRaises(IntegrationError):
            list(client.stream_statistics_analysis(
                provider_hint="grok / gork",
                note="请总结当前批次的主要风险。",
                statistics_context={
                    "summary": {"total_count": 16, "bad_count": 3},
                    "key_findings": ["某零件风险持续升高"],
                },
                model_context={
                    "display_name": "grok-4.20-fast",
                    "model_identifier": "grok-4.20-fast",
                    "protocol_type": "openai_responses",
                    "auth_mode": "authorization_bearer",
                    "base_url": "https://www.micuapi.ai/v1",
                    "user_agent": "codex_cli_rs/0.132.0",
                    "supports_vision": False,
                    "supports_stream": True,
                    "gateway_name": "gork",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-grok",
                },
            ))

        self.assertEqual(client.captured_urls, ["https://www.micuapi.ai/v1/responses"])
