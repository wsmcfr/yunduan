"""管理员用户管理服务回归测试。"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_settings
from src.core.errors import BadRequestError, ForbiddenError, NotFoundError
from src.core.security import hash_password, verify_password_and_update_hash
from src.db.base import Base
from src.db.models.company import Company
from src.db.models.detection_record import DetectionRecord
from src.db.models.enums import UserRole
from src.db.models.review_record import ReviewRecord
from src.db.models.user import User
from src.repositories.company_repository import CompanyRepository
from src.repositories.user_repository import UserRepository
from src.services.system_user_service import (
    DEFAULT_APPROVED_RESET_PASSWORD,
    SystemUserService,
)


class SystemUserServiceTestCase(unittest.TestCase):
    """覆盖公司管理员常用的成员管理与站内审批式改密动作。"""

    def setUp(self) -> None:
        """准备独立的内存数据库、配置环境与测试账号。"""

        os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
        os.environ.setdefault("JWT_SECRET_KEY", "system-user-test-secret")
        get_settings.cache_clear()

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        # 这里显式补齐与 User 关系删除相关的表，避免删除用户时因懒加载 reviews 关系而访问不存在的表。
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Company.__table__,
                User.__table__,
                DetectionRecord.__table__,
                ReviewRecord.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.session_factory()
        self.company_repository = CompanyRepository(self.db)
        self.user_repository = UserRepository(self.db)
        self.service = SystemUserService(self.db)

        self.company = self.company_repository.create(
            Company(
                name="演示公司",
                contact_name="联系人",
                note="系统用户管理测试公司",
                invite_code="USERMGT01",
                is_active=True,
                is_system_reserved=False,
            )
        )
        self.db.commit()
        self.db.refresh(self.company)

        self.admin_user = self.user_repository.create(
            User(
                username="admin-user",
                email="admin@example.com",
                password_hash=hash_password("AdminPass#2026"),
                password_changed_at=datetime.now(timezone.utc),
                display_name="管理员",
                role=UserRole.ADMIN,
                company_id=self.company.id,
                is_active=True,
                can_use_ai_analysis=True,
            )
        )
        self.target_user = self.user_repository.create(
            User(
                username="operator-user",
                email="operator@example.com",
                password_hash=hash_password("OriginalPass#2026"),
                password_changed_at=datetime.now(timezone.utc),
                display_name="操作员",
                role=UserRole.OPERATOR,
                company_id=self.company.id,
                is_active=True,
                can_use_ai_analysis=False,
            )
        )
        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.target_user)

    def tearDown(self) -> None:
        """释放测试数据库资源并清空配置缓存。"""

        self.db.close()
        self.engine.dispose()
        get_settings.cache_clear()

    def test_update_active_status_can_disable_and_enable_target_user(self) -> None:
        """管理员可以切换同公司成员的启停状态。"""

        disabled_user = self.service.update_active_status(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
            is_active=False,
        )
        self.assertFalse(disabled_user.is_active)

        enabled_user = self.service.update_active_status(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
            is_active=True,
        )
        self.assertTrue(enabled_user.is_active)

    def test_update_active_status_rejects_disabling_self(self) -> None:
        """管理员不能把自己停用，避免把自己锁死在公司外。"""

        with self.assertRaises(BadRequestError):
            self.service.update_active_status(
                company_id=self.company.id,
                current_user_id=self.admin_user.id,
                user_id=self.admin_user.id,
                is_active=False,
            )

    def test_submit_reset_request_marks_user_as_pending(self) -> None:
        """用户申请重置为默认密码时，应留下待审批快照。"""

        updated_user = self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="reset_to_default",
            new_password=None,
        )

        self.assertEqual(updated_user.password_change_request_status, "pending")
        self.assertEqual(updated_user.password_change_request_type, "reset_to_default")
        self.assertIsNone(updated_user.password_change_requested_password_encrypted)
        self.assertIsNotNone(updated_user.password_change_requested_at)
        self.assertIsNone(updated_user.password_change_reviewed_at)

    def test_submit_change_request_encrypts_requested_password(self) -> None:
        """用户申请改成指定新密码时，数据库里只应留下加密后的待审批口令。"""

        updated_user = self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="change_to_requested",
            new_password="RequestedPass#2026",
        )

        self.assertEqual(updated_user.password_change_request_status, "pending")
        self.assertEqual(updated_user.password_change_request_type, "change_to_requested")
        self.assertIsNotNone(updated_user.password_change_requested_password_encrypted)
        assert updated_user.password_change_requested_password_encrypted is not None
        self.assertEqual(
            self.service.secret_cipher.decrypt(updated_user.password_change_requested_password_encrypted),
            "RequestedPass#2026",
        )

    def test_submit_request_rejects_overwriting_pending_request(self) -> None:
        """同一用户已有待审批申请时，新的申请不应覆盖原来的审批快照。"""

        self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="reset_to_default",
            new_password=None,
        )

        with self.assertRaises(BadRequestError):
            self.service.submit_password_change_request(
                company_id=self.company.id,
                user_id=self.target_user.id,
                request_type="change_to_requested",
                new_password="RequestedPass#2026",
            )

    def test_approve_reset_request_rehashes_default_password_and_clears_transient_state(self) -> None:
        """管理员批准默认密码重置后，应真正写入新哈希并清空临时状态。"""

        self.target_user.password_reset_token_hash = "old-reset-token-hash"
        self.target_user.password_reset_sent_at = datetime.now(timezone.utc)
        self.target_user.password_reset_expires_at = datetime.now(timezone.utc)
        self.user_repository.save(self.target_user)
        self.db.commit()

        self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="reset_to_default",
            new_password=None,
        )

        refreshed_user, applied_password = self.service.approve_password_change_request(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
        )

        verified, _ = verify_password_and_update_hash(
            DEFAULT_APPROVED_RESET_PASSWORD,
            refreshed_user.password_hash,
        )
        self.assertTrue(verified)
        self.assertEqual(applied_password, DEFAULT_APPROVED_RESET_PASSWORD)
        self.assertEqual(refreshed_user.password_change_request_status, "approved")
        self.assertEqual(refreshed_user.password_change_request_type, "reset_to_default")
        self.assertIsNone(refreshed_user.password_change_requested_password_encrypted)
        self.assertIsNotNone(refreshed_user.password_change_reviewed_at)
        self.assertIsNone(refreshed_user.password_reset_token_hash)
        self.assertIsNone(refreshed_user.password_reset_sent_at)
        self.assertIsNone(refreshed_user.password_reset_expires_at)
        self.assertIsNotNone(refreshed_user.password_changed_at)

    def test_approve_change_request_applies_requested_password(self) -> None:
        """管理员批准“修改为新密码”后，应把待审批密码解密并写入正式哈希。"""

        self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="change_to_requested",
            new_password="RequestedPass#2026",
        )

        refreshed_user, applied_password = self.service.approve_password_change_request(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
        )

        verified, _ = verify_password_and_update_hash("RequestedPass#2026", refreshed_user.password_hash)
        self.assertTrue(verified)
        self.assertIsNone(applied_password)
        self.assertEqual(refreshed_user.password_change_request_status, "approved")
        self.assertEqual(refreshed_user.password_change_request_type, "change_to_requested")
        self.assertIsNone(refreshed_user.password_change_requested_password_encrypted)

    def test_admin_can_directly_reset_user_password_without_pending_request(self) -> None:
        """管理员无需等待用户申请，也可以直接把同公司成员密码重置为默认临时密码。"""

        self.target_user.password_reset_token_hash = "old-reset-token-hash"
        self.target_user.password_reset_sent_at = datetime.now(timezone.utc)
        self.target_user.password_reset_expires_at = datetime.now(timezone.utc)
        self.user_repository.save(self.target_user)
        self.db.commit()

        refreshed_user, applied_password = self.service.reset_user_password_to_default(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
        )

        verified, _ = verify_password_and_update_hash(
            DEFAULT_APPROVED_RESET_PASSWORD,
            refreshed_user.password_hash,
        )
        self.assertTrue(verified)
        self.assertEqual(applied_password, DEFAULT_APPROVED_RESET_PASSWORD)
        self.assertEqual(refreshed_user.password_change_request_status, "approved")
        self.assertEqual(refreshed_user.password_change_request_type, "reset_to_default")
        self.assertIsNone(refreshed_user.password_change_requested_password_encrypted)
        self.assertIsNotNone(refreshed_user.password_change_requested_at)
        self.assertIsNotNone(refreshed_user.password_change_reviewed_at)
        self.assertIsNone(refreshed_user.password_reset_token_hash)
        self.assertIsNone(refreshed_user.password_reset_sent_at)
        self.assertIsNone(refreshed_user.password_reset_expires_at)
        self.assertIsNotNone(refreshed_user.password_changed_at)

    def test_admin_direct_reset_closes_existing_pending_password_request(self) -> None:
        """管理员直接重置后，旧的待审批改密申请不应继续显示为可审批状态。"""

        self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="change_to_requested",
            new_password="RequestedPass#2026",
        )
        pending_requested_at = self.target_user.password_change_requested_at

        refreshed_user, applied_password = self.service.reset_user_password_to_default(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
        )

        requested_verified, _ = verify_password_and_update_hash(
            "RequestedPass#2026",
            refreshed_user.password_hash,
        )
        default_verified, _ = verify_password_and_update_hash(
            DEFAULT_APPROVED_RESET_PASSWORD,
            refreshed_user.password_hash,
        )
        self.assertFalse(requested_verified)
        self.assertTrue(default_verified)
        self.assertEqual(applied_password, DEFAULT_APPROVED_RESET_PASSWORD)
        self.assertEqual(refreshed_user.password_change_request_status, "approved")
        self.assertEqual(refreshed_user.password_change_request_type, "reset_to_default")
        self.assertEqual(refreshed_user.password_change_requested_at, pending_requested_at)
        self.assertIsNone(refreshed_user.password_change_requested_password_encrypted)

    def test_admin_direct_reset_rejects_self_operation(self) -> None:
        """管理员不能直接重置自己的密码，避免当前会话被自己误伤。"""

        with self.assertRaises(BadRequestError) as context:
            self.service.reset_user_password_to_default(
                company_id=self.company.id,
                current_user_id=self.admin_user.id,
                user_id=self.admin_user.id,
            )

        self.assertEqual(context.exception.code, "cannot_reset_password_self")

    def test_admin_direct_reset_rejects_default_admin(self) -> None:
        """平台默认管理员属于系统保留账号，不允许被公司管理员直接重置密码。"""

        default_admin = self.user_repository.create(
            User(
                username="default-admin",
                email="root@example.com",
                password_hash=hash_password("RootPass#2026"),
                password_changed_at=datetime.now(timezone.utc),
                display_name="默认管理员",
                role=UserRole.ADMIN,
                company_id=self.company.id,
                is_active=True,
                can_use_ai_analysis=True,
                is_default_admin=True,
            )
        )
        self.db.commit()
        self.db.refresh(default_admin)

        with self.assertRaises(ForbiddenError) as context:
            self.service.reset_user_password_to_default(
                company_id=self.company.id,
                current_user_id=self.admin_user.id,
                user_id=default_admin.id,
            )

        self.assertEqual(context.exception.code, "cannot_reset_password_default_admin")

    def test_admin_direct_reset_rejects_cross_company_user(self) -> None:
        """管理员只能重置当前公司内成员，跨公司目标统一表现为不存在。"""

        other_company = self.company_repository.create(
            Company(
                name="其他公司",
                contact_name="其他联系人",
                note="跨公司密码重置保护测试",
                invite_code="OTHER001",
                is_active=True,
                is_system_reserved=False,
            )
        )
        self.db.commit()
        self.db.refresh(other_company)
        outside_user = self.user_repository.create(
            User(
                username="outside-user",
                email="outside@example.com",
                password_hash=hash_password("OutsidePass#2026"),
                password_changed_at=datetime.now(timezone.utc),
                display_name="外部用户",
                role=UserRole.OPERATOR,
                company_id=other_company.id,
                is_active=True,
                can_use_ai_analysis=False,
            )
        )
        self.db.commit()
        self.db.refresh(outside_user)

        with self.assertRaises(NotFoundError) as context:
            self.service.reset_user_password_to_default(
                company_id=self.company.id,
                current_user_id=self.admin_user.id,
                user_id=outside_user.id,
            )

        self.assertEqual(context.exception.code, "user_not_found")

    def test_reject_change_request_clears_encrypted_pending_password(self) -> None:
        """管理员拒绝申请后，不应继续保留待审批密码密文。"""

        self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.target_user.id,
            request_type="change_to_requested",
            new_password="RequestedPass#2026",
        )

        refreshed_user = self.service.reject_password_change_request(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
        )

        original_verified, _ = verify_password_and_update_hash(
            "OriginalPass#2026",
            refreshed_user.password_hash,
        )
        self.assertTrue(original_verified)
        self.assertEqual(refreshed_user.password_change_request_status, "rejected")
        self.assertEqual(refreshed_user.password_change_request_type, "change_to_requested")
        self.assertIsNone(refreshed_user.password_change_requested_password_encrypted)
        self.assertIsNotNone(refreshed_user.password_change_reviewed_at)

    def test_approve_request_rejects_self_operation(self) -> None:
        """管理员不能审批自己的密码申请，避免出现自审自批。"""

        self.service.submit_password_change_request(
            company_id=self.company.id,
            user_id=self.admin_user.id,
            request_type="reset_to_default",
            new_password=None,
        )

        with self.assertRaises(BadRequestError):
            self.service.approve_password_change_request(
                company_id=self.company.id,
                current_user_id=self.admin_user.id,
                user_id=self.admin_user.id,
            )

    def test_delete_user_removes_target_account(self) -> None:
        """管理员可以删除同公司普通成员。"""

        self.service.delete_user(
            company_id=self.company.id,
            current_user_id=self.admin_user.id,
            user_id=self.target_user.id,
        )

        self.assertIsNone(self.user_repository.get_by_id(self.target_user.id))
