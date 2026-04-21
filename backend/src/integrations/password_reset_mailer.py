"""密码重置邮件发送集成。"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from src.core.config import Settings, get_settings
from src.core.errors import IntegrationError
from src.db.models.user import User


class PasswordResetMailer:
    """负责把密码重置链接投递到用户邮箱。"""

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化邮件发送配置。"""

        self.settings = settings or get_settings()

    def is_enabled(self) -> bool:
        """判断当前环境是否已经具备密码找回邮件通道。"""

        return bool(
            self.settings.smtp_host.strip()
            and self.settings.smtp_from_email.strip()
            and self.settings.public_app_url.strip()
        )

    def _build_reset_url(self, token: str) -> str:
        """拼装前端密码重置页面链接。"""

        base_url = self.settings.public_app_url.strip().rstrip("/")
        return f"{base_url}/reset-password?token={quote(token)}"

    def send_password_reset_mail(self, *, user: User, reset_token: str) -> None:
        """发送密码重置邮件。"""

        if not self.is_enabled():
            raise IntegrationError(
                code="password_reset_channel_unavailable",
                message="当前环境尚未配置密码找回邮件通道，请联系管理员。",
            )

        reset_url = self._build_reset_url(reset_token)
        message = EmailMessage()
        message["Subject"] = "云端检测系统密码重置"
        message["From"] = (
            f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            if self.settings.smtp_from_name.strip()
            else self.settings.smtp_from_email
        )
        message["To"] = user.email or ""
        message.set_content(
            "\n".join(
                [
                    f"{user.display_name}，你好：",
                    "",
                    "系统已收到你的密码重置申请。",
                    "请在链接有效期内打开下面地址并设置新密码：",
                    reset_url,
                    "",
                    "如果这不是你的操作，请忽略本邮件。",
                ]
            )
        )

        try:
            if self.settings.smtp_use_ssl:
                smtp_client = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=15)
            else:
                smtp_client = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15)

            with smtp_client as client:
                client.ehlo()
                if self.settings.smtp_use_tls and not self.settings.smtp_use_ssl:
                    client.starttls()
                    client.ehlo()
                if self.settings.smtp_username.strip():
                    client.login(self.settings.smtp_username, self.settings.smtp_password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise IntegrationError(
                code="password_reset_mail_send_failed",
                message="密码重置邮件发送失败，请稍后重试。",
            ) from exc
