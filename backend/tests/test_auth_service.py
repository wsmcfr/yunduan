"""认证服务与密码重置关键回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.errors import ConflictError, UnauthorizedError
from src.core.security import (
    create_access_token,
    decode_access_token,
    hash_password_reset_token,
    validate_token_freshness,
    verify_password_and_update_hash,
)
from src.db.base import Base
from src.db.models.user import User
from src.repositories.user_repository import UserRepository
from src.services.auth_service import AuthService


class StubPasswordResetMailer:
    """通过桩对象记录密码重置邮件，而不触发真实外发。"""

    def __init__(self) -> None:
        """初始化测试期的已发送消息列表。"""

        self.sent_messages: list[dict[str, str]] = []

    def is_enabled(self) -> bool:
        """测试场景固定认为邮件能力可用。"""

        return True

    def send_password_reset_mail(self, *, user: User, reset_token: str) -> None:
        """记录本次发送的目标邮箱与原始令牌。"""

        self.sent_messages.append(
            {
                "email": user.email or "",
                "token": reset_token,
            }
        )


class AuthServiceTestCase(unittest.TestCase):
    """覆盖正式认证体系的核心安全回归。"""

    def setUp(self) -> None:
        """为每个测试准备独立的内存数据库。"""

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine, tables=[User.__table__])
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.session_factory()
        self.mailer = StubPasswordResetMailer()
        self.service = AuthService(self.db, password_reset_mailer=self.mailer)
        self.service.settings.allow_public_registration = True
        self.user_repository = UserRepository(self.db)

    def tearDown(self) -> None:
        """释放数据库连接和内存引擎。"""

        self.db.close()
        self.engine.dispose()

    def _register_demo_user(self) -> tuple[str, User]:
        """创建一个标准测试用户，便于后续复用。"""

        token, _, user = self.service.register(
            username="demo-user",
            display_name="演示用户",
            email="Demo@Example.com",
            password="StrongPass#2026",
        )
        return token, user

    def test_register_hashes_password_and_normalizes_email(self) -> None:
        """注册后数据库中只能看到规整后的邮箱和密码哈希。"""

        _, user = self._register_demo_user()
        persisted_user = self.user_repository.get_by_id(user.id)

        self.assertIsNotNone(persisted_user)
        assert persisted_user is not None
        self.assertEqual(persisted_user.email, "demo@example.com")
        self.assertNotEqual(persisted_user.password_hash, "StrongPass#2026")
        verified, _ = verify_password_and_update_hash("StrongPass#2026", persisted_user.password_hash)
        self.assertTrue(verified)

    def test_register_rejects_duplicate_email(self) -> None:
        """邮箱唯一性冲突必须被明确拒绝。"""

        self._register_demo_user()

        with self.assertRaises(ConflictError):
            self.service.register(
                username="another-user",
                display_name="另一个用户",
                email="demo@example.com",
                password="AnotherPass#2026",
            )

    def test_request_password_reset_only_persists_token_hash(self) -> None:
        """忘记密码流程只能把令牌哈希落库，不能落明文 token。"""

        _, user = self._register_demo_user()
        self.service.request_password_reset("demo@example.com")
        persisted_user = self.user_repository.get_by_id(user.id)

        self.assertEqual(len(self.mailer.sent_messages), 1)
        assert persisted_user is not None
        sent_token = self.mailer.sent_messages[0]["token"]
        self.assertIsNotNone(persisted_user.password_reset_token_hash)
        self.assertNotEqual(persisted_user.password_reset_token_hash, sent_token)
        self.assertEqual(persisted_user.password_reset_token_hash, hash_password_reset_token(sent_token))
        self.assertIsNotNone(persisted_user.password_reset_expires_at)

    def test_reset_password_invalidates_old_password_and_clears_reset_state(self) -> None:
        """重置成功后旧密码必须失效，并清空一次性令牌状态。"""

        _, user = self._register_demo_user()
        persisted_user = self.user_repository.get_by_id(user.id)
        assert persisted_user is not None
        previous_hash = persisted_user.password_hash

        self.service.request_password_reset("demo@example.com")
        reset_token = self.mailer.sent_messages[0]["token"]
        self.service.reset_password(token=reset_token, new_password="NewStrongPass#2026")

        refreshed_user = self.user_repository.get_by_id(user.id)
        assert refreshed_user is not None
        self.assertNotEqual(refreshed_user.password_hash, previous_hash)
        self.assertIsNone(refreshed_user.password_reset_token_hash)
        self.assertIsNone(refreshed_user.password_reset_sent_at)
        self.assertIsNone(refreshed_user.password_reset_expires_at)

        with self.assertRaises(UnauthorizedError):
            self.service.login("demo-user", "StrongPass#2026")

        next_token, _, _ = self.service.login("demo-user", "NewStrongPass#2026")
        self.assertTrue(next_token)

    def test_password_change_invalidates_old_session_token(self) -> None:
        """密码更新后，旧令牌必须被判定为失效。"""

        token, user = self._register_demo_user()
        self.service.request_password_reset("demo@example.com")
        reset_token = self.mailer.sent_messages[0]["token"]
        self.service.reset_password(token=reset_token, new_password="NewStrongPass#2026")

        refreshed_user = self.user_repository.get_by_id(user.id)
        assert refreshed_user is not None

        token_payload = decode_access_token(token)
        issued_at = datetime.fromtimestamp(
            int(token_payload["issued_at_ms"]) / 1000,
            tz=timezone.utc,
        )

        with self.assertRaises(UnauthorizedError):
            validate_token_freshness(
                token_payload,
                password_changed_at=issued_at + timedelta(seconds=2),
            )

    def test_token_freshness_allows_small_clock_skew(self) -> None:
        """令牌时间与密码变更时间存在轻微精度偏差时，不应误判为失效。"""

        token, _ = create_access_token(subject="123")
        token_payload = decode_access_token(token)
        issued_at = datetime.fromtimestamp(
            int(token_payload["issued_at_ms"]) / 1000,
            tz=timezone.utc,
        )

        # 模拟数据库秒级精度、序列化或时钟边界带来的轻微偏差。
        validate_token_freshness(
            token_payload,
            password_changed_at=issued_at + timedelta(milliseconds=500),
        )

        with self.assertRaises(UnauthorizedError):
            validate_token_freshness(
                token_payload,
                password_changed_at=issued_at + timedelta(seconds=2),
            )
