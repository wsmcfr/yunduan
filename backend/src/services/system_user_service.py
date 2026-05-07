"""管理员用户管理服务。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.errors import BadRequestError, ForbiddenError, NotFoundError
from src.core.secret_cipher import SecretCipher
from src.core.security import hash_password
from src.db.models.enums import UserRole
from src.db.models.user import User
from src.repositories.user_repository import UserRepository

# 管理员批准“重置为默认密码”后，系统统一回落到这个临时口令。
# 用户下一次登录后应立即再次修改成自己的正式密码。
DEFAULT_APPROVED_RESET_PASSWORD = "Q123456@"


class SystemUserService:
    """封装系统设置页中的用户查询、权限管理与站内审批式改密逻辑。"""

    def __init__(self, db: Session) -> None:
        """保存当前请求的数据库会话、仓储与敏感字段加密器。"""

        self.db = db
        self.user_repository = UserRepository(db)
        self.secret_cipher = SecretCipher()

    def _get_scoped_user(self, *, company_id: int | None, user_id: int) -> User:
        """按公司边界加载目标用户，避免跨公司误操作。"""

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(code="user_not_found", message="目标用户不存在。")
        if company_id is not None and user.company_id != company_id:
            raise NotFoundError(code="user_not_found", message="目标用户不存在。")
        return user

    def _ensure_manageable_user(self, *, user: User, current_user_id: int, action_label: str) -> None:
        """校验当前管理员可以对目标用户执行高风险管理动作。"""

        if user.id == current_user_id:
            raise BadRequestError(
                code=f"cannot_{action_label}_self",
                message="不能对当前登录账号执行该操作。",
            )
        if user.is_default_admin:
            raise ForbiddenError(
                code=f"cannot_{action_label}_default_admin",
                message="平台默认管理员账号不允许执行该操作。",
            )

    def _clear_password_reset_state(self, user: User) -> None:
        """清空邮箱找回密码链路里残留的一次性令牌状态。"""

        user.password_reset_token_hash = None
        user.password_reset_sent_at = None
        user.password_reset_expires_at = None

    def _set_password_request_snapshot(
        self,
        *,
        user: User,
        status: str | None,
        request_type: str | None,
        encrypted_password: str | None,
        requested_at: datetime | None,
        reviewed_at: datetime | None,
    ) -> None:
        """统一写入站内审批式改密申请快照。"""

        user.password_change_request_status = status
        user.password_change_request_type = request_type
        user.password_change_requested_password_encrypted = encrypted_password
        user.password_change_requested_at = requested_at
        user.password_change_reviewed_at = reviewed_at

    def _require_pending_password_request(self, user: User) -> str:
        """确保目标用户当前确实存在一条待审批的密码申请。"""

        if user.password_change_request_status != "pending" or not user.password_change_request_type:
            raise BadRequestError(
                code="password_change_request_not_pending",
                message="当前用户没有待审批的密码申请。",
            )

        return user.password_change_request_type

    def list_users(
        self,
        *,
        company_id: int | None,
        keyword: str | None,
        role: UserRole | None,
        can_use_ai_analysis: bool | None,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[User]]:
        """按管理员筛选条件分页返回用户列表。"""

        return self.user_repository.list_users(
            company_id=company_id,
            keyword=keyword,
            role=role,
            can_use_ai_analysis=can_use_ai_analysis,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

    def update_ai_permission(
        self,
        *,
        company_id: int | None,
        user_id: int,
        can_use_ai_analysis: bool,
    ) -> User:
        """更新指定用户的 AI 分析使用权限。"""

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        user.can_use_ai_analysis = can_use_ai_analysis
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_active_status(
        self,
        *,
        company_id: int | None,
        current_user_id: int,
        user_id: int,
        is_active: bool,
    ) -> User:
        """更新指定用户的启停状态。"""

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        self._ensure_manageable_user(
            user=user,
            current_user_id=current_user_id,
            action_label="change_status",
        )

        user.is_active = is_active
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(
        self,
        *,
        company_id: int | None,
        current_user_id: int,
        user_id: int,
    ) -> None:
        """彻底删除指定用户账号。"""

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        self._ensure_manageable_user(
            user=user,
            current_user_id=current_user_id,
            action_label="delete",
        )

        self.user_repository.delete(user)
        self.db.commit()

    def get_password_change_request_info(
        self,
        *,
        company_id: int | None,
        user_id: int,
    ) -> User:
        """读取当前用户最新的站内改密申请状态。"""

        return self._get_scoped_user(company_id=company_id, user_id=user_id)

    def submit_password_change_request(
        self,
        *,
        company_id: int | None,
        user_id: int,
        request_type: str,
        new_password: str | None,
    ) -> User:
        """由用户本人提交站内密码申请，等待公司管理员审批。"""

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        # 待审批申请只允许存在一条，避免用户在管理员尚未处理时反复覆盖目标密码。
        if user.password_change_request_status == "pending":
            raise BadRequestError(
                code="password_change_request_already_pending",
                message="当前已有待审批的密码申请，请等待管理员处理后再重新提交。",
            )

        requested_at = datetime.now(timezone.utc)

        if request_type == "reset_to_default":
            encrypted_password = None
        elif request_type == "change_to_requested":
            if not new_password:
                raise BadRequestError(
                    code="password_change_request_password_required",
                    message="申请修改为新密码时，必须填写目标密码。",
                )
            encrypted_password = self.secret_cipher.encrypt(new_password)
        else:
            raise BadRequestError(
                code="password_change_request_type_invalid",
                message="不支持当前密码申请类型。",
            )

        self._set_password_request_snapshot(
            user=user,
            status="pending",
            request_type=request_type,
            encrypted_password=encrypted_password,
            requested_at=requested_at,
            reviewed_at=None,
        )
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def approve_password_change_request(
        self,
        *,
        company_id: int | None,
        current_user_id: int,
        user_id: int,
    ) -> tuple[User, str | None]:
        """由公司管理员批准用户的站内改密申请，并真正写入新密码哈希。"""

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        self._ensure_manageable_user(
            user=user,
            current_user_id=current_user_id,
            action_label="approve_password_change_request",
        )

        request_type = self._require_pending_password_request(user)
        reviewed_at = datetime.now(timezone.utc)
        applied_password: str | None = None

        if request_type == "reset_to_default":
            applied_password = DEFAULT_APPROVED_RESET_PASSWORD
            user.password_hash = hash_password(DEFAULT_APPROVED_RESET_PASSWORD)
        elif request_type == "change_to_requested":
            encrypted_password = user.password_change_requested_password_encrypted
            if not encrypted_password:
                raise BadRequestError(
                    code="password_change_request_payload_missing",
                    message="当前待审批申请缺少目标密码，无法批准。",
                )
            requested_password = self.secret_cipher.decrypt(encrypted_password)
            user.password_hash = hash_password(requested_password)
        else:
            raise BadRequestError(
                code="password_change_request_type_invalid",
                message="不支持当前密码申请类型。",
            )

        user.password_changed_at = reviewed_at
        self._clear_password_reset_state(user)
        self._set_password_request_snapshot(
            user=user,
            status="approved",
            request_type=request_type,
            encrypted_password=None,
            requested_at=user.password_change_requested_at,
            reviewed_at=reviewed_at,
        )
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user, applied_password

    def reset_user_password_to_default(
        self,
        *,
        company_id: int | None,
        current_user_id: int,
        user_id: int,
    ) -> tuple[User, str]:
        """由公司管理员直接把成员密码重置为系统默认临时密码。

        主要流程：
        1. 先按公司边界加载目标用户，避免跨公司重置密码。
        2. 复用高风险账号保护，禁止管理员重置自己或平台默认管理员。
        3. 写入默认临时密码哈希，并清理邮箱找回密码令牌与站内待审批密文。
        4. 返回本次实际生效的临时密码，供前端只在成功提示里短暂展示。
        """

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        self._ensure_manageable_user(
            user=user,
            current_user_id=current_user_id,
            action_label="reset_password",
        )

        reviewed_at = datetime.now(timezone.utc)
        # 如果原来没有用户申请，这里用管理员操作时间作为请求时间，保证列表里有完整审计快照。
        requested_at = user.password_change_requested_at or reviewed_at

        user.password_hash = hash_password(DEFAULT_APPROVED_RESET_PASSWORD)
        user.password_changed_at = reviewed_at
        self._clear_password_reset_state(user)
        self._set_password_request_snapshot(
            user=user,
            status="approved",
            request_type="reset_to_default",
            encrypted_password=None,
            requested_at=requested_at,
            reviewed_at=reviewed_at,
        )
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user, DEFAULT_APPROVED_RESET_PASSWORD

    def reject_password_change_request(
        self,
        *,
        company_id: int | None,
        current_user_id: int,
        user_id: int,
    ) -> User:
        """由公司管理员拒绝用户的站内改密申请，并清理待审批敏感口令。"""

        user = self._get_scoped_user(company_id=company_id, user_id=user_id)
        self._ensure_manageable_user(
            user=user,
            current_user_id=current_user_id,
            action_label="reject_password_change_request",
        )

        request_type = self._require_pending_password_request(user)
        reviewed_at = datetime.now(timezone.utc)

        self._set_password_request_snapshot(
            user=user,
            status="rejected",
            request_type=request_type,
            encrypted_password=None,
            requested_at=user.password_change_requested_at,
            reviewed_at=reviewed_at,
        )
        self.user_repository.save(user)
        self.db.commit()
        self.db.refresh(user)
        return user
