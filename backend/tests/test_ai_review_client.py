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
            },
            {
                "id": 12,
                "file_kind": "source",
                "bucket_name": "demo-bucket-1250000000",
                "region": "ap-guangzhou",
                "object_key": "detections/demo/source/raw.png",
                "uploaded_at": datetime(2026, 4, 20, 2, 1, 24, tzinfo=timezone.utc),
                "preview_url": "https://demo-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/detections/demo/source/raw.png",
            },
        ]

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
                "base_url": "https://www.openclaudecode.cn/v1",
                "user_agent": "codex_cli_rs/0.77.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "OpenClaudeCode",
                "api_key": "sk-demo-codex",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["answer"], "这是来自 Codex 协议的真实回答。")
        self.assertEqual(client.captured_url, "https://www.openclaudecode.cn/v1/responses")
        self.assertEqual(
            client.captured_headers["Authorization"],  # type: ignore[index]
            "Bearer sk-demo-codex",
        )
        self.assertIn("codex_cli_rs", client.captured_headers["User-Agent"])  # type: ignore[index]
        self.assertEqual(client.captured_payload["model"], "gpt-5.4")  # type: ignore[index]
        self.assertEqual(len(client.captured_payload["input"]), 2)  # type: ignore[index]
        self.assertEqual(
            client.captured_payload["input"][-1]["content"][1]["type"],  # type: ignore[index]
            "input_image",
        )

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

    def test_chat_about_record_falls_back_to_openai_compatible_when_openclaudecode_responses_returns_invalid_json(self) -> None:
        """验证 OpenClaudeCode `/responses` 返回非 JSON 时，会自动回退到 Chat Completions。"""

        client = InvalidJsonFallbackStubAIReviewClient()
        client.next_response = {
            "choices": [
                {
                    "message": {
                        "content": "已自动回退到 Chat Completions 并返回回答。",
                    }
                }
            ]
        }

        response = client.chat_about_record(
            record_id=1,
            provider_hint="grok / gork",
            question="请说明为什么统计 AI 会失败。",
            history=[],
            context=self.context,
            referenced_files=self.referenced_files,
            model_context={
                "display_name": "grok-4.20-fast",
                "model_identifier": "grok-4.20-fast",
                "protocol_type": "openai_responses",
                "auth_mode": "authorization_bearer",
                "base_url": "https://www.openclaudecode.cn/v1",
                "user_agent": "codex_cli_rs/0.77.0 (Windows 10.0.26100; x86_64) WindowsTerminal",
                "supports_vision": True,
                "supports_stream": True,
                "gateway_name": "gork",
                "gateway_vendor": "openclaudecode",
                "api_key": "sk-demo-grok",
            },
        )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["answer"], "已自动回退到 Chat Completions 并返回回答。")
        self.assertEqual(
            client.captured_urls,
            [
                "https://www.openclaudecode.cn/v1/responses",
                "https://www.openclaudecode.cn/v1/chat/completions",
            ],
        )

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
                "base_url": "https://www.openclaudecode.cn",
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
        self.assertEqual(client.captured_url, "https://www.openclaudecode.cn/v1/messages")

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
                    "base_url": "https://www.openclaudecode.cn",
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
        self.assertEqual(client.captured_url, "https://www.openclaudecode.cn/v1/messages")

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
                    "base_url": "https://www.openclaudecode.cn/v1",
                    "user_agent": "codex_cli_rs/0.77.0",
                    "supports_vision": False,
                    "supports_stream": True,
                    "gateway_name": "OpenClaudeCode",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-codex",
                },
            )
        )

        self.assertEqual("".join(output_chunks), full_answer)
        self.assertEqual(client.captured_url, "https://www.openclaudecode.cn/v1/responses")
        self.assertTrue(client.captured_payload["stream"])  # type: ignore[index]

    def test_stream_statistics_analysis_falls_back_when_openclaudecode_responses_returns_invalid_json(self) -> None:
        """验证统计流式分析在 `/responses` 返回非 JSON 时，会自动改走 Chat Completions。"""

        client = InvalidJsonStreamingFallbackStubAIReviewClient()
        fallback_url = "https://www.openclaudecode.cn/v1/chat/completions"
        client.stream_event_map[fallback_url] = [
            (
                None,
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "回退后的第一段。",
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
                                "content": "回退后的第二段。",
                            }
                        }
                    ]
                },
            ),
        ]

        output_chunks = list(
            client.stream_statistics_analysis(
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
                    "base_url": "https://www.openclaudecode.cn/v1",
                    "user_agent": "codex_cli_rs/0.77.0",
                    "supports_vision": False,
                    "supports_stream": True,
                    "gateway_name": "gork",
                    "gateway_vendor": "openclaudecode",
                    "api_key": "sk-demo-grok",
                },
            )
        )

        self.assertEqual(output_chunks, ["回退后的第一段。", "回退后的第二段。"])
        self.assertEqual(
            client.captured_urls,
            [
                "https://www.openclaudecode.cn/v1/responses",
                "https://www.openclaudecode.cn/v1/chat/completions",
            ],
        )
