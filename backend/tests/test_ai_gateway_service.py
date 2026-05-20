"""AI 网关运行时配置服务测试。"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.db.models.ai_gateway import AIGateway
from src.db.models.ai_model_profile import AIModelProfile
from src.db.models.company import Company
from src.db.models.enums import (
    AIAuthMode,
    AIGatewayVendor,
    AIModelVendor,
    AIProtocolType,
)
from src.integrations.ai_model_discovery_client import OPENCLAUDECODE_CODEX_UA
from src.services.ai_gateway_service import AIGatewayService


class FakeSecretCipher:
    """测试用密钥加解密器，避免单元测试依赖真实 `.env` 配置。"""

    def encrypt(self, plaintext: str) -> str:
        """返回带前缀的可预测密文。"""

        return f"encrypted:{plaintext}"

    def decrypt(self, token: str) -> str:
        """还原测试密文中的明文 API Key。"""

        return token.removeprefix("encrypted:")


class AIGatewayServiceTestCase(unittest.TestCase):
    """验证 AI 网关运行时上下文的协议与 URL 归一化行为。"""

    def setUp(self) -> None:
        """为每个测试准备只包含 AI 网关配置所需表结构的内存数据库。"""

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Company.__table__,
                AIGateway.__table__,
                AIModelProfile.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.session_factory()
        self.cipher = FakeSecretCipher()
        self.service = AIGatewayService(self.db, cipher=self.cipher)
        self.company = self._create_company()

    def tearDown(self) -> None:
        """释放测试数据库连接，避免测试之间互相污染。"""

        self.db.close()
        self.engine.dispose()

    def _create_company(self) -> Company:
        """创建标准测试公司，AI 网关和模型配置必须归属到该公司。"""

        company = Company(
            name="AI 网关测试公司",
            contact_name="测试联系人",
            note="用于 AI 网关服务测试。",
            invite_code="AIGWTEST",
            is_active=True,
            is_system_reserved=False,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def _create_openclaudecode_gateway(self) -> AIGateway:
        """创建米醋/OpenClaudeCode 网关配置。"""

        api_key = "sk-test-openclaudecode"
        gateway = AIGateway(
            company_id=self.company.id,
            name="米醋 API",
            vendor=AIGatewayVendor.OPENCLAUDECODE,
            official_url="https://www.micuapi.ai",
            base_url="https://www.micuapi.ai",
            note=None,
            is_enabled=True,
            is_custom=False,
            api_key_encrypted=self.cipher.encrypt(api_key),
            api_key_last4=api_key[-4:],
        )
        self.db.add(gateway)
        self.db.commit()
        self.db.refresh(gateway)
        return gateway

    def _create_model(
        self,
        *,
        gateway: AIGateway,
        model_identifier: str,
        upstream_vendor: AIModelVendor,
        protocol_type: AIProtocolType,
        user_agent: str | None = None,
    ) -> AIModelProfile:
        """创建测试模型配置，允许故意保存错误协议来验证运行时纠偏。"""

        model = AIModelProfile(
            gateway_id=gateway.id,
            display_name=model_identifier,
            upstream_vendor=upstream_vendor,
            protocol_type=protocol_type,
            auth_mode=AIAuthMode.AUTHORIZATION_BEARER,
            base_url_override=None,
            user_agent=user_agent,
            model_identifier=model_identifier,
            supports_vision=True,
            supports_stream=True,
            is_enabled=True,
            note=None,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def test_openclaudecode_gpt_model_runtime_forces_responses_protocol(self) -> None:
        """验证米醋/OpenClaudeCode 的 GPT/Codex 模型运行时必须走 `/v1/responses`。

        这覆盖生产里最容易出现的问题：自动探测或历史配置把 `gpt-5.4`
        保存成 `openai_compatible`，导致请求落到 `/v1/chat/completions`，从而
        无法使用 Responses 路径和对应缓存能力。
        """

        gateway = self._create_openclaudecode_gateway()
        model = self._create_model(
            gateway=gateway,
            model_identifier="gpt-5.4",
            upstream_vendor=AIModelVendor.CUSTOM,
            protocol_type=AIProtocolType.OPENAI_COMPATIBLE,
            user_agent="Mozilla/5.0",
        )

        runtime_context = self.service.build_runtime_model_context(
            company_id=self.company.id,
            model_id=model.id,
        )

        self.assertEqual(runtime_context["protocol_type"], "openai_responses")
        self.assertEqual(runtime_context["base_url"], "https://www.micuapi.ai/v1")
        self.assertEqual(runtime_context["user_agent"], OPENCLAUDECODE_CODEX_UA)
        self.assertIn("codex_cli_rs/0.132.0", str(runtime_context["user_agent"]))

    def test_openclaudecode_grok_model_runtime_keeps_configured_protocol(self) -> None:
        """验证 Grok 不会被 GPT/Codex 纠偏规则误改成 Responses。"""

        gateway = self._create_openclaudecode_gateway()
        model = self._create_model(
            gateway=gateway,
            model_identifier="grok-4.20-fast",
            upstream_vendor=AIModelVendor.CUSTOM,
            protocol_type=AIProtocolType.ANTHROPIC_MESSAGES,
            user_agent="claude-cli/2.0.76",
        )

        runtime_context = self.service.build_runtime_model_context(
            company_id=self.company.id,
            model_id=model.id,
        )

        self.assertEqual(runtime_context["protocol_type"], "anthropic_messages")
        self.assertEqual(runtime_context["base_url"], "https://www.micuapi.ai")


if __name__ == "__main__":
    unittest.main()
