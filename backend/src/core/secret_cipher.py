"""服务端密钥字段加解密工具。"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import get_settings
from src.core.errors import IntegrationError


class SecretCipher:
    """负责对 API Key 等敏感字段做服务端加密存储。"""

    def __init__(self, secret: str | None = None) -> None:
        """初始化对称加密器。

        主要流程：
        1. 优先使用显式传入的密钥，便于单元测试和后续扩展。
        2. 未传入时优先读取 `SECRET_ENCRYPTION_KEY`。
        3. 如果未单独配置，则回退到 `JWT_SECRET_KEY` 派生固定密钥。
        """

        settings = get_settings()
        raw_secret = secret or settings.secret_encryption_key or settings.jwt_secret_key
        self._fernet = Fernet(self._normalize_fernet_key(raw_secret))

    def _normalize_fernet_key(self, secret: str) -> bytes:
        """把任意稳定字符串转换成 Fernet 可接受的 32 字节密钥。"""

        candidate = secret.encode("utf-8")

        try:
            Fernet(candidate)
            return candidate
        except (TypeError, ValueError):
            # 允许运维直接给一段普通字符串，再稳定派生成 Fernet key，
            # 这样既兼容现有 `.env` 配置，也避免因为密钥格式不对导致服务无法启动。
            digest = hashlib.sha256(candidate).digest()
            return base64.urlsafe_b64encode(digest)

    def encrypt(self, plaintext: str) -> str:
        """加密明文敏感信息并返回可持久化的 token。"""

        normalized_text = plaintext.strip()
        if not normalized_text:
            raise ValueError("待加密的敏感信息不能为空。")

        return self._fernet.encrypt(normalized_text.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        """解密数据库中的敏感字段。

        如果解密失败，说明服务端配置密钥和数据库中的历史数据不匹配，
        这属于部署级问题，必须明确暴露而不是悄悄忽略。
        """

        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise IntegrationError(
                code="secret_decrypt_failed",
                message="服务端敏感配置解密失败，请检查 SECRET_ENCRYPTION_KEY 配置。",
            ) from exc
