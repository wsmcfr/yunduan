"""AI 模型自动探测客户端。"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from src.core.errors import BadRequestError, IntegrationError
from src.core.logging import get_logger
from src.db.models.enums import AIAuthMode, AIGatewayVendor, AIModelVendor, AIProtocolType

logger = get_logger(__name__)

# OpenClaudeCode 本地文档明确要求不同外接类型携带不同 UA。
OPENCLAUDECODE_CLAUDE_UA = "claude-cli/2.0.76 (external, cli)"
OPENCLAUDECODE_CODEX_UA = "codex_cli_rs/0.77.0 (Windows 10.0.26100; x86_64) WindowsTerminal"
OPENCLAUDECODE_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0"
)


class AIModelDiscoveryClient:
    """根据网关 URL、鉴权方式和密钥自动探测可用模型。"""

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        """初始化自动探测客户端。"""

        self.timeout_seconds = timeout_seconds

    def _build_headers(
        self,
        *,
        auth_mode: AIAuthMode,
        api_key: str,
        user_agent: str | None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """按鉴权方式组装 GET 探测请求头。"""

        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if auth_mode in {AIAuthMode.AUTHORIZATION_BEARER, AIAuthMode.BOTH}:
            headers["Authorization"] = f"Bearer {api_key}"
        if auth_mode in {AIAuthMode.X_API_KEY, AIAuthMode.BOTH}:
            headers["x-api-key"] = api_key
        if user_agent:
            headers["User-Agent"] = user_agent
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _append_query_api_key(self, *, url: str, auth_mode: AIAuthMode, api_key: str) -> str:
        """在 `query_api_key` 模式下把密钥拼进 URL。"""

        if auth_mode != AIAuthMode.QUERY_API_KEY:
            return url

        parsed_url = urlparse(url)
        next_query = urlencode({"key": api_key})
        merged_query = f"{parsed_url.query}&{next_query}" if parsed_url.query else next_query
        return urlunparse(parsed_url._replace(query=merged_query))

    def _get_json(self, *, url: str, headers: dict[str, str]) -> dict[str, Any]:
        """发起 GET 请求并返回 JSON。

        自动探测本质上是“试探不同供应商的 models 接口”，
        某个探测策略失败并不一定意味着整个网关不可用，
        因此由上层决定是否忽略单个策略失败。
        """

        request = Request(url, headers=headers, method="GET")

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            raise IntegrationError(
                code="ai_models_discovery_http_error",
                message=f"探测模型列表失败，HTTP {exc.code}。",
                details={
                    "status_code": exc.code,
                    "endpoint": url,
                    "response": response_text[:600],
                },
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise IntegrationError(
                code="ai_models_discovery_network_error",
                message="探测模型列表时网络请求失败，请检查 URL、网络和密钥是否正确。",
                details={
                    "endpoint": url,
                    "reason": str(exc),
                },
            ) from exc

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise IntegrationError(
                code="ai_models_discovery_invalid_json",
                message="模型探测接口返回了无法解析的 JSON。",
                details={
                    "endpoint": url,
                    "response": response_text[:600],
                },
            ) from exc

    def _build_openai_like_urls(self, *, base_url: str) -> list[str]:
        """生成 OpenAI-compatible 风格的模型列表候选 URL。"""

        normalized_base_url = base_url.rstrip("/")
        candidate_urls = [f"{normalized_base_url}/models"]

        parsed_url = urlparse(normalized_base_url)
        path = parsed_url.path.rstrip("/")
        if not path.endswith("/v1") and not path.endswith("/v4"):
            candidate_urls.append(f"{normalized_base_url}/v1/models")

        deduped_urls: list[str] = []
        for item in candidate_urls:
            if item not in deduped_urls:
                deduped_urls.append(item)
        return deduped_urls

    def _build_anthropic_urls(self, *, base_url: str) -> list[str]:
        """生成 Anthropic Messages 风格的模型列表候选 URL。"""

        normalized_base_url = base_url.rstrip("/")
        candidate_urls = [f"{normalized_base_url}/v1/models"]

        if normalized_base_url.endswith("/v1"):
            candidate_urls.insert(0, f"{normalized_base_url}/models")

        deduped_urls: list[str] = []
        for item in candidate_urls:
            if item not in deduped_urls:
                deduped_urls.append(item)
        return deduped_urls

    def _build_gemini_urls(self, *, base_url: str) -> list[str]:
        """生成 Gemini GenerateContent 风格的模型列表候选 URL。"""

        normalized_base_url = base_url.rstrip("/")
        candidate_urls = [f"{normalized_base_url}/models"]

        parsed_url = urlparse(normalized_base_url)
        path = parsed_url.path.rstrip("/")
        if not path.endswith("/v1beta") and not path.endswith("/v1"):
            candidate_urls.append(f"{normalized_base_url}/v1beta/models")

        deduped_urls: list[str] = []
        for item in candidate_urls:
            if item not in deduped_urls:
                deduped_urls.append(item)
        return deduped_urls

    def _strip_url_suffix(self, *, url: str, suffix: str) -> str:
        """从 URL 路径尾部裁掉指定后缀。"""

        normalized_url = url.rstrip("/")
        parsed_url = urlparse(normalized_url)
        normalized_path = parsed_url.path.rstrip("/")
        if not normalized_path.endswith(suffix):
            return normalized_url

        next_path = normalized_path[: -len(suffix)]
        return urlunparse(parsed_url._replace(path=next_path))

    def _resolve_runtime_base_url_for_openai_like(self, *, candidate_url: str) -> str:
        """根据探测命中的 `/models` 地址还原 OpenAI 风格运行时基地址。

        OpenAI Compatible / Responses 在运行时会继续拼接：
        - `/chat/completions`
        - `/responses`

        因此如果探测实际命中的是 `/v1/models`，运行时基地址也必须保留 `/v1`。
        """

        return self._strip_url_suffix(url=candidate_url, suffix="/models")

    def _resolve_runtime_base_url_for_anthropic(self, *, base_url: str) -> str:
        """将 Anthropic 风格基地址统一归一成“不带 /v1”的形式。

        因为运行时会固定再拼一次 `/v1/messages`，如果这里保留 `/v1` 就会变成 `/v1/v1/messages`。
        """

        return self._strip_url_suffix(url=base_url, suffix="/v1")

    def _resolve_runtime_base_url_for_gemini(self, *, candidate_url: str) -> str:
        """根据 Gemini 探测命中的 `/models` 地址还原运行时基地址。"""

        return self._strip_url_suffix(url=candidate_url, suffix="/models")

    def _infer_model_vendor(
        self,
        *,
        gateway_vendor: AIGatewayVendor,
        protocol_type: AIProtocolType,
        model_identifier: str,
    ) -> AIModelVendor:
        """根据网关品牌、协议和模型名推断上游模型品牌。"""

        normalized_identifier = model_identifier.lower()

        if "claude" in normalized_identifier or protocol_type == AIProtocolType.ANTHROPIC_MESSAGES:
            return AIModelVendor.CLAUDE
        if "gemini" in normalized_identifier or protocol_type == AIProtocolType.GEMINI_GENERATE_CONTENT:
            return AIModelVendor.GEMINI
        if normalized_identifier.startswith("glm") or "bigmodel" in normalized_identifier:
            return AIModelVendor.GLM
        if "kimi" in normalized_identifier or "moonshot" in normalized_identifier:
            return AIModelVendor.KIMI
        if "deepseek" in normalized_identifier:
            return AIModelVendor.DEEPSEEK
        if "minimax" in normalized_identifier or normalized_identifier.startswith("m1"):
            return AIModelVendor.MINMAX
        if normalized_identifier.startswith("gpt") or normalized_identifier.startswith("o") or "codex" in normalized_identifier:
            return AIModelVendor.CODEX

        if gateway_vendor == AIGatewayVendor.ANTHROPIC:
            return AIModelVendor.CLAUDE
        if gateway_vendor == AIGatewayVendor.GOOGLE:
            return AIModelVendor.GEMINI
        if gateway_vendor == AIGatewayVendor.ZHIPU:
            return AIModelVendor.GLM
        if gateway_vendor == AIGatewayVendor.MOONSHOT:
            return AIModelVendor.KIMI
        if gateway_vendor == AIGatewayVendor.MINMAX:
            return AIModelVendor.MINMAX
        if gateway_vendor == AIGatewayVendor.DEEPSEEK:
            return AIModelVendor.DEEPSEEK
        if gateway_vendor == AIGatewayVendor.OPENAI:
            return AIModelVendor.CODEX

        return AIModelVendor.CUSTOM

    def _infer_supports_vision(
        self,
        *,
        model_identifier: str,
        upstream_vendor: AIModelVendor,
    ) -> bool:
        """用保守规则推断模型是否支持视觉。"""

        normalized_identifier = model_identifier.lower()
        if any(keyword in normalized_identifier for keyword in ["vision", "vl", "omni", "4o", "2.5", "gemini"]):
            return True
        return upstream_vendor in {AIModelVendor.CLAUDE, AIModelVendor.GEMINI}

    def _build_candidate(
        self,
        *,
        gateway_vendor: AIGatewayVendor,
        protocol_type: AIProtocolType,
        auth_mode: AIAuthMode,
        base_url: str,
        model_identifier: str,
        display_name: str | None,
        user_agent: str | None,
        source_label: str,
    ) -> dict[str, Any]:
        """把不同供应商返回的模型条目整理成统一结构。"""

        upstream_vendor = self._infer_model_vendor(
            gateway_vendor=gateway_vendor,
            protocol_type=protocol_type,
            model_identifier=model_identifier,
        )
        return {
            "model_identifier": model_identifier,
            "display_name": (display_name or model_identifier).strip(),
            "upstream_vendor": upstream_vendor,
            "protocol_type": protocol_type,
            "auth_mode": auth_mode,
            "base_url": base_url,
            "user_agent": user_agent,
            "supports_vision": self._infer_supports_vision(
                model_identifier=model_identifier,
                upstream_vendor=upstream_vendor,
            ),
            "supports_stream": True,
            "source_label": source_label,
        }

    def _discover_openai_like_models(
        self,
        *,
        gateway_vendor: AIGatewayVendor,
        base_url: str,
        api_key: str,
        auth_mode: AIAuthMode,
        protocol_type: AIProtocolType,
        user_agent: str | None,
        source_label: str,
    ) -> list[dict[str, Any]]:
        """通过 OpenAI-compatible 的 `/models` 接口探测模型。"""

        last_error: Exception | None = None
        for candidate_url in self._build_openai_like_urls(base_url=base_url):
            request_url = self._append_query_api_key(
                url=candidate_url,
                auth_mode=auth_mode,
                api_key=api_key,
            )
            try:
                response_data = self._get_json(
                    url=request_url,
                    headers=self._build_headers(
                        auth_mode=auth_mode,
                        api_key=api_key,
                        user_agent=user_agent,
                    ),
                )
                items = response_data.get("data") or []
                discovered_items = [
                    self._build_candidate(
                        gateway_vendor=gateway_vendor,
                        protocol_type=protocol_type,
                        auth_mode=auth_mode,
                        base_url=self._resolve_runtime_base_url_for_openai_like(
                            candidate_url=candidate_url,
                        ),
                        model_identifier=str(item.get("id") or "").strip(),
                        display_name=str(item.get("id") or "").strip(),
                        user_agent=user_agent,
                        source_label=source_label,
                    )
                    for item in items
                    if str(item.get("id") or "").strip()
                ]
                if discovered_items:
                    return discovered_items
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        return []

    def _discover_anthropic_models(
        self,
        *,
        gateway_vendor: AIGatewayVendor,
        base_url: str,
        api_key: str,
        auth_mode: AIAuthMode,
        user_agent: str | None,
        source_label: str,
    ) -> list[dict[str, Any]]:
        """通过 Anthropic `/v1/models` 接口探测模型。"""

        last_error: Exception | None = None
        for candidate_url in self._build_anthropic_urls(base_url=base_url):
            request_url = self._append_query_api_key(
                url=candidate_url,
                auth_mode=auth_mode,
                api_key=api_key,
            )
            try:
                response_data = self._get_json(
                    url=request_url,
                    headers=self._build_headers(
                        auth_mode=auth_mode,
                        api_key=api_key,
                        user_agent=user_agent,
                        extra_headers={"anthropic-version": "2023-06-01"},
                    ),
                )
                items = response_data.get("data") or []
                discovered_items = [
                    self._build_candidate(
                        gateway_vendor=gateway_vendor,
                        protocol_type=AIProtocolType.ANTHROPIC_MESSAGES,
                        auth_mode=auth_mode,
                        base_url=self._resolve_runtime_base_url_for_anthropic(
                            base_url=base_url,
                        ),
                        model_identifier=str(item.get("id") or "").strip(),
                        display_name=str(item.get("display_name") or item.get("id") or "").strip(),
                        user_agent=user_agent,
                        source_label=source_label,
                    )
                    for item in items
                    if str(item.get("id") or "").strip()
                ]
                if discovered_items:
                    return discovered_items
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        return []

    def _discover_gemini_models(
        self,
        *,
        base_url: str,
        api_key: str,
        auth_mode: AIAuthMode,
        user_agent: str | None,
        source_label: str,
    ) -> list[dict[str, Any]]:
        """通过 Gemini `/models` 接口探测模型。"""

        last_error: Exception | None = None
        for candidate_url in self._build_gemini_urls(base_url=base_url):
            request_url = self._append_query_api_key(
                url=candidate_url,
                auth_mode=auth_mode,
                api_key=api_key,
            )
            try:
                response_data = self._get_json(
                    url=request_url,
                    headers=self._build_headers(
                        auth_mode=auth_mode,
                        api_key=api_key,
                        user_agent=user_agent,
                    ),
                )
                items = response_data.get("models") or []
                discovered_items = [
                    self._build_candidate(
                        gateway_vendor=AIGatewayVendor.GOOGLE,
                        protocol_type=AIProtocolType.GEMINI_GENERATE_CONTENT,
                        auth_mode=auth_mode,
                        base_url=self._resolve_runtime_base_url_for_gemini(
                            candidate_url=candidate_url,
                        ),
                        model_identifier=(
                            str(item.get("baseModelId") or "").strip()
                            or str(item.get("name") or "").replace("models/", "").strip()
                        ),
                        display_name=str(item.get("displayName") or item.get("name") or "").strip(),
                        user_agent=user_agent,
                        source_label=source_label,
                    )
                    for item in items
                    if (
                        str(item.get("baseModelId") or "").strip()
                        or str(item.get("name") or "").replace("models/", "").strip()
                    )
                ]
                if discovered_items:
                    return discovered_items
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        return []

    def _dedupe_candidates(self, *, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """对多策略探测结果做去重。"""

        unique_items: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str, str]] = set()

        for item in items:
            dedupe_key = (
                str(item["model_identifier"]),
                str(item["protocol_type"].value),
                str(item["auth_mode"].value),
                str(item["source_label"]),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            unique_items.append(item)

        return unique_items

    def discover_models(
        self,
        *,
        gateway_vendor: AIGatewayVendor,
        base_url: str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """根据网关品牌选择探测策略。

        当前策略设计原则：
        1. 优先按官方协议探测。
        2. 对 relay / custom / openclaudecode 这种多协议场景，允许并行尝试多个协议。
        3. 单个策略失败不立刻终止，只要有一个成功即可返回。
        """

        normalized_base_url = base_url.strip().rstrip("/")
        normalized_api_key = api_key.strip()
        if not normalized_base_url:
            raise BadRequestError(code="ai_gateway_base_url_required", message="网关基础 URL 不能为空。")
        if not normalized_api_key:
            raise BadRequestError(code="api_key_required", message="请填写有效的 API Key。")

        discovered_items: list[dict[str, Any]] = []
        collected_errors: list[str] = []

        def run_probe(probe_label: str, probe_func) -> None:  # type: ignore[no-untyped-def]
            """执行单个探测策略，并把失败原因记下来用于最终提示。"""

            try:
                discovered_items.extend(probe_func())
            except Exception as exc:
                logger.warning("ai_models.discovery_failed probe=%s error=%s", probe_label, exc)
                collected_errors.append(f"{probe_label}: {exc}")

        if gateway_vendor == AIGatewayVendor.OPENAI:
            run_probe(
                "openai-models",
                lambda: self._discover_openai_like_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    protocol_type=AIProtocolType.OPENAI_RESPONSES,
                    user_agent=None,
                    source_label="OpenAI Models API",
                ),
            )
        elif gateway_vendor == AIGatewayVendor.ANTHROPIC:
            run_probe(
                "anthropic-models",
                lambda: self._discover_anthropic_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.X_API_KEY,
                    user_agent=None,
                    source_label="Anthropic Models API",
                ),
            )
        elif gateway_vendor == AIGatewayVendor.GOOGLE:
            run_probe(
                "gemini-models",
                lambda: self._discover_gemini_models(
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.QUERY_API_KEY,
                    user_agent=None,
                    source_label="Gemini Models API",
                ),
            )
        elif gateway_vendor in {
            AIGatewayVendor.ZHIPU,
            AIGatewayVendor.MOONSHOT,
            AIGatewayVendor.MINMAX,
            AIGatewayVendor.DEEPSEEK,
        }:
            run_probe(
                "openai-compatible-models",
                lambda: self._discover_openai_like_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    protocol_type=AIProtocolType.OPENAI_COMPATIBLE,
                    user_agent=None,
                    source_label="OpenAI-Compatible Models API",
                ),
            )
        elif gateway_vendor == AIGatewayVendor.OPENCLAUDECODE:
            run_probe(
                "openclaudecode-claude",
                lambda: self._discover_anthropic_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    user_agent=OPENCLAUDECODE_CLAUDE_UA,
                    source_label="OpenClaudeCode Claude 外接",
                ),
            )
            run_probe(
                "openclaudecode-codex",
                lambda: self._discover_openai_like_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    protocol_type=AIProtocolType.OPENAI_RESPONSES,
                    user_agent=OPENCLAUDECODE_CODEX_UA,
                    source_label="OpenClaudeCode Codex 外接",
                ),
            )
            run_probe(
                "openclaudecode-domestic",
                lambda: self._discover_openai_like_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    protocol_type=AIProtocolType.OPENAI_COMPATIBLE,
                    user_agent=OPENCLAUDECODE_BROWSER_UA,
                    source_label="OpenClaudeCode 国产模型外接",
                ),
            )
        else:
            run_probe(
                "relay-openai-compatible",
                lambda: self._discover_openai_like_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    protocol_type=AIProtocolType.OPENAI_COMPATIBLE,
                    user_agent=None,
                    source_label="通用 OpenAI-Compatible 探测",
                ),
            )
            run_probe(
                "relay-anthropic",
                lambda: self._discover_anthropic_models(
                    gateway_vendor=gateway_vendor,
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
                    user_agent=None,
                    source_label="通用 Anthropic 探测",
                ),
            )
            run_probe(
                "relay-gemini",
                lambda: self._discover_gemini_models(
                    base_url=normalized_base_url,
                    api_key=normalized_api_key,
                    auth_mode=AIAuthMode.QUERY_API_KEY,
                    user_agent=None,
                    source_label="通用 Gemini 探测",
                ),
            )

        deduped_items = self._dedupe_candidates(items=discovered_items)
        if deduped_items:
            return deduped_items

        raise IntegrationError(
            code="ai_models_discovery_failed",
            message="未能从当前 URL 和密钥探测到可用模型，请检查网关地址、密钥、鉴权方式或供应商类型。",
            details={
                "gateway_vendor": gateway_vendor.value,
                "base_url": normalized_base_url,
                "errors": collected_errors,
            },
        )
