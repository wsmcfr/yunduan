"""AI 模型自动探测客户端测试。"""

from __future__ import annotations

import unittest
from urllib.parse import urlparse, parse_qs

from src.db.models.enums import AIGatewayVendor
from src.integrations.ai_model_discovery_client import (
    AIModelDiscoveryClient,
    OPENCLAUDECODE_CODEX_UA,
)


class StubAIModelDiscoveryClient(AIModelDiscoveryClient):
    """通过覆写 GET 层来验证探测逻辑而不发真实网络请求。"""

    def __init__(self) -> None:
        """初始化一个记录请求上下文的桩客户端。"""

        super().__init__()
        self.captured_urls: list[str] = []
        self.captured_headers: list[dict[str, str]] = []
        self.response_map: dict[str, dict] = {}

    def _get_json(self, *, url: str, headers: dict[str, str]) -> dict:  # type: ignore[override]
        """记录请求并返回预设响应。"""

        self.captured_urls.append(url)
        self.captured_headers.append(headers)
        if url not in self.response_map:
            raise RuntimeError(f"未为 {url} 预置返回值。")
        return self.response_map[url]


class AIModelDiscoveryClientTestCase(unittest.TestCase):
    """验证不同供应商的模型探测策略。"""

    def test_discover_openai_models_uses_models_endpoint(self) -> None:
        """OpenAI 官方应通过 `/v1/models` 获取模型列表。"""

        client = StubAIModelDiscoveryClient()
        client.response_map["https://api.openai.com/v1/models"] = {
            "data": [
                {"id": "gpt-5.4"},
                {"id": "gpt-5.4-mini"},
            ]
        }

        items = client.discover_models(
            gateway_vendor=AIGatewayVendor.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="sk-openai-demo",
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["model_identifier"], "gpt-5.4")
        self.assertEqual(items[0]["protocol_type"].value, "openai_responses")
        self.assertEqual(
            client.captured_headers[0]["Authorization"],
            "Bearer sk-openai-demo",
        )

    def test_discover_anthropic_models_uses_x_api_key(self) -> None:
        """Anthropic 官方应通过 `/v1/models` 与 `x-api-key` 获取模型列表。"""

        client = StubAIModelDiscoveryClient()
        client.response_map["https://api.anthropic.com/v1/models"] = {
            "data": [
                {
                    "id": "claude-sonnet-4-20250514",
                    "display_name": "Claude Sonnet 4",
                }
            ]
        }

        items = client.discover_models(
            gateway_vendor=AIGatewayVendor.ANTHROPIC,
            base_url="https://api.anthropic.com",
            api_key="sk-ant-demo",
        )

        self.assertEqual(items[0]["model_identifier"], "claude-sonnet-4-20250514")
        self.assertEqual(items[0]["upstream_vendor"].value, "claude")
        self.assertEqual(client.captured_headers[0]["x-api-key"], "sk-ant-demo")
        self.assertEqual(client.captured_headers[0]["anthropic-version"], "2023-06-01")

    def test_discover_gemini_models_uses_query_api_key(self) -> None:
        """Gemini 官方应通过 `?key=` 探测模型列表。"""

        client = StubAIModelDiscoveryClient()
        response_url = "https://generativelanguage.googleapis.com/v1beta/models?key=gemini-secret"
        client.response_map[response_url] = {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "baseModelId": "gemini-2.5-flash",
                    "displayName": "Gemini 2.5 Flash",
                }
            ]
        }

        items = client.discover_models(
            gateway_vendor=AIGatewayVendor.GOOGLE,
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key="gemini-secret",
        )

        self.assertEqual(items[0]["model_identifier"], "gemini-2.5-flash")
        self.assertEqual(items[0]["auth_mode"].value, "query_api_key")
        parsed_url = urlparse(client.captured_urls[0])
        self.assertEqual(parse_qs(parsed_url.query)["key"][0], "gemini-secret")

    def test_discover_openclaudecode_runs_multiple_ua_strategies(self) -> None:
        """OpenClaudeCode 需要按不同外接类型带不同 UA 探测。"""

        client = StubAIModelDiscoveryClient()
        shared_url = "https://www.openclaudecode.cn/v1/models"
        client.response_map[shared_url] = {
            "data": [
                {"id": "gpt-5.4"},
            ]
        }
        client.response_map["https://www.openclaudecode.cn/models"] = {
            "data": []
        }

        items = client.discover_models(
            gateway_vendor=AIGatewayVendor.OPENCLAUDECODE,
            base_url="https://www.openclaudecode.cn",
            api_key="sk-opencc-demo",
        )

        self.assertTrue(any(item["model_identifier"] == "gpt-5.4" for item in items))
        self.assertTrue(any(headers.get("User-Agent") == OPENCLAUDECODE_CODEX_UA for headers in client.captured_headers))

    def test_discover_openclaudecode_retains_grok_under_dedicated_source_label(self) -> None:
        """Grok 模型应落到独立的 Grok 外接分组，而不是继续混在 Claude 组里。"""

        client = StubAIModelDiscoveryClient()
        shared_url = "https://www.openclaudecode.cn/v1/models"
        client.response_map[shared_url] = {
            "data": [
                {"id": "grok-4.20-fast"},
            ]
        }
        client.response_map["https://www.openclaudecode.cn/models"] = {
            "data": []
        }

        items = client.discover_models(
            gateway_vendor=AIGatewayVendor.OPENCLAUDECODE,
            base_url="https://www.openclaudecode.cn",
            api_key="sk-opencc-demo",
        )

        grok_items = [item for item in items if item["model_identifier"] == "grok-4.20-fast"]
        self.assertTrue(any(item["source_label"] == "OpenClaudeCode Grok 外接" for item in grok_items))
        self.assertFalse(any(item["source_label"] == "OpenClaudeCode Claude 外接" for item in grok_items))
        self.assertFalse(any(item["source_label"] == "OpenClaudeCode Codex 外接" for item in grok_items))
        self.assertFalse(any(item["source_label"] == "OpenClaudeCode 国产模型外接" for item in grok_items))
