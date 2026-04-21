"""密码重置邮件发送集成。"""

from __future__ import annotations

from html import escape
import smtplib
from email.message import EmailMessage
from urllib.parse import quote, urlsplit, urlunsplit

from src.core.config import Settings, get_settings
from src.core.errors import IntegrationError
from src.db.models.user import User


class PasswordResetMailer:
    """负责把密码重置链接投递到用户邮箱。"""

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化邮件发送配置。"""

        self.settings = settings or get_settings()

    def _normalize_public_app_url(self, candidate: str | None) -> str | None:
        """校验并规整公开前端地址，避免把无效值拼进邮件链接。"""

        normalized_candidate = (candidate or "").strip()
        if not normalized_candidate:
            return None

        parsed_url = urlsplit(normalized_candidate)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            return None

        return urlunsplit((parsed_url.scheme, parsed_url.netloc, "", "", ""))

    def _resolve_public_app_url(self, public_app_url_override: str | None = None) -> str | None:
        """解析本次发信应使用的公开前端地址。

        请求上下文推断出的地址优先级高于环境变量，便于公网部署时自动生成正确链接。
        """

        override_url = self._normalize_public_app_url(public_app_url_override)
        if override_url is not None:
            return override_url

        return self._normalize_public_app_url(self.settings.public_app_url)

    def is_enabled(self, public_app_url_override: str | None = None) -> bool:
        """判断当前环境是否已经具备密码找回邮件通道。"""

        return bool(
            self.settings.smtp_host.strip()
            and self.settings.smtp_from_email.strip()
            and self._resolve_public_app_url(public_app_url_override)
        )

    def _build_reset_url(
        self,
        token: str,
        *,
        public_app_url_override: str | None = None,
    ) -> str:
        """拼装前端密码重置页面链接。"""

        base_url = self._resolve_public_app_url(public_app_url_override)
        if base_url is None:
            raise IntegrationError(
                code="password_reset_channel_unavailable",
                message="当前环境尚未配置可用的密码找回地址，请联系管理员。",
            )

        return f"{base_url}/reset-password?token={quote(token)}"

    def _build_text_content(self, *, user: User, reset_url: str, reset_token: str) -> str:
        """构造纯文本邮件正文，兼容不支持 HTML 的客户端。"""

        expire_minutes = self.settings.password_reset_token_expire_minutes
        return "\n".join(
            [
                f"{user.display_name}，你好：",
                "",
                "系统已收到你的密码重置申请。",
                f"请在 {expire_minutes} 分钟内打开下面链接并设置新密码：",
                reset_url,
                "",
                "如果浏览器无法直接打开链接，也可以手动复制下面的一次性重置令牌：",
                reset_token,
                "",
                "如果这不是你的操作，请忽略本邮件。",
            ]
        )

    def _build_html_content(self, *, user: User, reset_url: str, reset_token: str) -> str:
        """构造 HTML 邮件正文，提升公网环境下的点击体验。"""

        escaped_display_name = escape(user.display_name)
        escaped_reset_url = escape(reset_url, quote=True)
        escaped_reset_token = escape(reset_token)
        expire_minutes = self.settings.password_reset_token_expire_minutes

        return (
            "<html><body style=\"font-family:Arial,'Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;\">"
            f"<p>{escaped_display_name}，你好：</p>"
            "<p>系统已收到你的密码重置申请。</p>"
            f"<p>请在 <strong>{expire_minutes} 分钟</strong> 内点击下面按钮并设置新密码：</p>"
            f"<p><a href=\"{escaped_reset_url}\" "
            "style=\"display:inline-block;padding:10px 18px;background:#1840d8;color:#ffffff;"
            "text-decoration:none;border-radius:8px;\">立即重置密码</a></p>"
            f"<p>如果按钮无法点击，也可以直接打开此链接：<br><a href=\"{escaped_reset_url}\">{escaped_reset_url}</a></p>"
            f"<p>如果需要手动粘贴令牌，请复制这一段：<br><code>{escaped_reset_token}</code></p>"
            "<p>如果这不是你的操作，请忽略本邮件。</p>"
            "</body></html>"
        )

    def send_password_reset_mail(
        self,
        *,
        user: User,
        reset_token: str,
        public_app_url_override: str | None = None,
    ) -> None:
        """发送密码重置邮件。"""

        if not self.is_enabled(public_app_url_override):
            raise IntegrationError(
                code="password_reset_channel_unavailable",
                message="当前环境尚未配置密码找回邮件通道，请联系管理员。",
            )

        reset_url = self._build_reset_url(
            reset_token,
            public_app_url_override=public_app_url_override,
        )
        message = EmailMessage()
        message["Subject"] = "云端检测系统密码重置"
        message["From"] = (
            f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            if self.settings.smtp_from_name.strip()
            else self.settings.smtp_from_email
        )
        message["To"] = user.email or ""
        message.set_content(
            self._build_text_content(
                user=user,
                reset_url=reset_url,
                reset_token=reset_token,
            )
        )
        message.add_alternative(
            self._build_html_content(
                user=user,
                reset_url=reset_url,
                reset_token=reset_token,
            ),
            subtype="html",
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
