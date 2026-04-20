"""服务端敏感字段加解密测试。"""

from __future__ import annotations

import unittest

from src.core.errors import IntegrationError
from src.core.secret_cipher import SecretCipher


class SecretCipherTestCase(unittest.TestCase):
    """验证 API Key 加解密不会泄露且能明确暴露错误配置。"""

    def test_encrypt_and_decrypt_round_trip(self) -> None:
        """同一把密钥加密后必须能稳定解回原文。"""

        cipher = SecretCipher(secret="unit-test-secret")
        encrypted_value = cipher.encrypt("sk-demo-secret")

        self.assertNotEqual(encrypted_value, "sk-demo-secret")
        self.assertEqual(cipher.decrypt(encrypted_value), "sk-demo-secret")

    def test_decrypt_with_wrong_secret_raises_integration_error(self) -> None:
        """当服务端密钥不匹配时，必须明确抛出部署级错误。"""

        writer_cipher = SecretCipher(secret="writer-secret")
        reader_cipher = SecretCipher(secret="reader-secret")
        encrypted_value = writer_cipher.encrypt("sk-demo-secret")

        with self.assertRaises(IntegrationError):
            reader_cipher.decrypt(encrypted_value)
