"""密码重置邮件发送器回归测试。"""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from src.integrations.password_reset_mailer import PasswordResetMailer


class PasswordResetMailerTestCase(unittest.TestCase):
    """覆盖密码重置邮件发送器的公开地址解析规则。"""

    def _build_mailer(self, **overrides: object) -> PasswordResetMailer:
        """构造一个只包含必需字段的伪配置对象。"""

        settings = SimpleNamespace(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="demo@example.com",
            smtp_password="secret",
            smtp_from_email="demo@example.com",
            smtp_from_name="云端检测系统",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            public_app_url="",
            password_reset_token_expire_minutes=30,
        )
        for field_name, field_value in overrides.items():
            setattr(settings, field_name, field_value)
        return PasswordResetMailer(settings=settings)  # type: ignore[arg-type]

    def test_is_enabled_accepts_request_derived_public_url_override(self) -> None:
        """即使环境变量未显式配置公开地址，也允许使用本次请求推断出的公网地址。"""

        mailer = self._build_mailer(public_app_url="")

        self.assertTrue(mailer.is_enabled("https://prod.example.com"))

    def test_build_reset_url_prefers_override_over_env_value(self) -> None:
        """请求上下文提供的公网地址应覆盖旧的环境变量地址。"""

        mailer = self._build_mailer(public_app_url="http://localhost:5173")

        reset_url = mailer._build_reset_url(
            "demo-token",
            public_app_url_override="https://prod.example.com",
        )

        self.assertEqual(
            reset_url,
            "https://prod.example.com/reset-password?token=demo-token",
        )

    def test_text_content_contains_link_and_manual_token(self) -> None:
        """邮件正文既要能直接点击，也要能支持用户手动复制令牌。"""

        mailer = self._build_mailer()
        user = SimpleNamespace(display_name="演示用户")

        content = mailer._build_text_content(
            user=user,  # type: ignore[arg-type]
            reset_url="https://prod.example.com/reset-password?token=abc",
            reset_token="abc",
        )

        self.assertIn("https://prod.example.com/reset-password?token=abc", content)
        self.assertIn("abc", content)
