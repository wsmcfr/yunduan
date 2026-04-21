"""公司管理与管理员申请审批服务。"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import BadRequestError, ConflictError, IntegrationError, NotFoundError
from src.db.models.company import Company
from src.db.models.enums import AdminApplicationStatus, UserRole
from src.db.models.file_object import FileObject
from src.db.models.user import User
from src.integrations.cos_client import CosClient
from src.repositories.company_repository import CompanyRepository
from src.repositories.user_repository import UserRepository


class CompanyService:
    """封装公司邀请码、管理员审批、停用与彻底删除流程。"""

    _invite_code_alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def __init__(self, db: Session, cos_client: CosClient | None = None) -> None:
        """初始化公司管理依赖。"""

        self.db = db
        self.company_repository = CompanyRepository(db)
        self.user_repository = UserRepository(db)
        self.cos_client = cos_client or CosClient()

    def _normalize_company_name(self, company_name: str) -> str:
        """规整公司名称。"""

        normalized_value = company_name.strip()
        if len(normalized_value) < 2:
            raise BadRequestError(code="company_name_invalid", message="公司名称至少需要 2 个字符。")
        return normalized_value

    def _generate_invite_code(self, *, length: int = 10) -> str:
        """生成公司固定邀请码。

        邀请码由大写字母和数字组成，避免容易混淆的字符，便于人工口头传递。
        """

        return "".join(secrets.choice(self._invite_code_alphabet) for _ in range(length))

    def _generate_unique_invite_code(self) -> str:
        """生成当前数据库内唯一的邀请码。"""

        for _ in range(20):
            invite_code = self._generate_invite_code()
            if self.company_repository.get_by_invite_code(invite_code) is None:
                return invite_code

        raise BadRequestError(code="invite_code_generation_failed", message="公司邀请码生成失败，请稍后重试。")

    def get_company_by_id(self, company_id: int) -> Company:
        """获取指定公司，不存在时抛出明确错误。"""

        company = self.company_repository.get_by_id(company_id)
        if company is None:
            raise NotFoundError(code="company_not_found", message="公司不存在。")
        return company

    def get_current_company(self, *, company_id: int) -> Company:
        """获取当前登录用户所属公司。"""

        return self.get_company_by_id(company_id)

    def list_companies(
        self,
        *,
        keyword: str | None,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[Company]]:
        """分页返回平台管理员视角下的公司列表。"""

        total, items = self.company_repository.list_companies(
            keyword=keyword,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        usage_map = self.company_repository.summarize_company_usage(
            company_ids=[item.id for item in items],
        )
        for item in items:
            usage = usage_map.get(item.id, {})
            setattr(item, "user_count", int(usage.get("user_count", 0) or 0))
            setattr(item, "part_count", int(usage.get("part_count", 0) or 0))
            setattr(item, "device_count", int(usage.get("device_count", 0) or 0))
            setattr(item, "record_count", int(usage.get("record_count", 0) or 0))
            setattr(item, "gateway_count", int(usage.get("gateway_count", 0) or 0))
        return total, items

    def list_admin_applications(
        self,
        *,
        keyword: str | None,
        application_status: AdminApplicationStatus | None,
        skip: int,
        limit: int,
    ) -> tuple[int, list[User]]:
        """分页返回新公司管理员申请列表。"""

        return self.user_repository.list_admin_application_users(
            keyword=keyword,
            application_status=application_status,
            skip=skip,
            limit=limit,
        )

    def approve_admin_application(self, *, user_id: int) -> User:
        """批准管理员申请并自动创建新公司。"""

        applicant = self.user_repository.get_by_id(user_id)
        if applicant is None:
            raise NotFoundError(code="user_not_found", message="目标用户不存在。")
        if applicant.role != UserRole.ADMIN:
            raise BadRequestError(code="invalid_admin_application", message="该用户不是管理员申请账号。")
        if applicant.admin_application_status != AdminApplicationStatus.PENDING:
            raise BadRequestError(code="admin_application_not_pending", message="当前申请不是待审批状态。")
        if applicant.company_id is not None:
            raise BadRequestError(code="admin_application_already_bound", message="该申请账号已绑定公司。")
        if not applicant.requested_company_name:
            raise BadRequestError(code="company_name_missing", message="申请资料缺少公司名称。")

        normalized_company_name = self._normalize_company_name(applicant.requested_company_name)
        if self.company_repository.get_by_name(normalized_company_name) is not None:
            raise ConflictError(code="company_name_exists", message="公司名称已存在，请先修改申请资料。")

        company = Company(
            name=normalized_company_name,
            contact_name=(applicant.requested_company_contact_name or "").strip() or None,
            note=(applicant.requested_company_note or "").strip() or None,
            invite_code=self._generate_unique_invite_code(),
            is_active=True,
            is_system_reserved=False,
        )
        self.company_repository.create(company)

        applicant.company_id = company.id
        applicant.is_active = True
        applicant.can_use_ai_analysis = True
        applicant.admin_application_status = AdminApplicationStatus.APPROVED
        self.user_repository.save(applicant)

        self.db.commit()
        self.db.refresh(applicant)
        return applicant

    def reject_admin_application(self, *, user_id: int) -> User:
        """拒绝待审批的新公司管理员申请。"""

        applicant = self.user_repository.get_by_id(user_id)
        if applicant is None:
            raise NotFoundError(code="user_not_found", message="目标用户不存在。")
        if applicant.role != UserRole.ADMIN:
            raise BadRequestError(code="invalid_admin_application", message="该用户不是管理员申请账号。")
        if applicant.admin_application_status != AdminApplicationStatus.PENDING:
            raise BadRequestError(code="admin_application_not_pending", message="当前申请不是待审批状态。")

        applicant.admin_application_status = AdminApplicationStatus.REJECTED
        self.user_repository.save(applicant)
        self.db.commit()
        self.db.refresh(applicant)
        return applicant

    def reset_invite_code(self, *, company_id: int) -> Company:
        """为指定公司重置固定邀请码。"""

        company = self.get_company_by_id(company_id)
        if not company.is_active:
            raise BadRequestError(code="company_inactive", message="公司已停用，不能重置邀请码。")

        company.invite_code = self._generate_unique_invite_code()
        self.company_repository.save(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def deactivate_company(self, *, company_id: int) -> Company:
        """停用公司，阻止其成员继续登录和继续使用业务功能。"""

        company = self.get_company_by_id(company_id)
        if company.is_system_reserved:
            raise BadRequestError(code="system_company_protected", message="系统保留公司不允许停用。")

        company.is_active = False
        self.company_repository.save(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def _delete_company_cos_objects(self, *, company_id: int) -> None:
        """删除公司在 COS 中占用的对象。

        这里先删对象再删数据库，避免数据库已清空而对象仍残留在 COS 中。
        """

        file_rows = self.db.execute(
            select(
                FileObject.bucket_name,
                FileObject.region,
                FileObject.object_key,
            ).where(FileObject.company_id == company_id)
        ).all()
        unique_files = {
            (str(row.bucket_name), str(row.region), str(row.object_key))
            for row in file_rows
            if row.bucket_name and row.region and row.object_key
        }

        failed_objects: list[str] = []
        for bucket_name, region, object_key in unique_files:
            try:
                self.cos_client.delete_object(
                    bucket_name=bucket_name,
                    region=region,
                    object_key=object_key,
                )
            except IntegrationError:
                failed_objects.append(object_key)

        if failed_objects:
            raise IntegrationError(
                code="company_storage_cleanup_failed",
                message="公司对象存储清理失败，已中止彻底删除。",
                details={
                    "failed_object_count": len(failed_objects),
                    "sample_object_keys": failed_objects[:5],
                },
            )

    def purge_company(self, *, company_id: int, confirm_name: str) -> None:
        """彻底删除公司及其全部成员、业务数据和对象存储占用。"""

        company = self.get_company_by_id(company_id)
        if company.is_system_reserved:
            raise BadRequestError(code="system_company_protected", message="系统保留公司不允许彻底删除。")
        if company.is_active:
            raise BadRequestError(code="company_must_be_deactivated_first", message="请先停用公司，再执行彻底删除。")

        normalized_confirm_name = confirm_name.strip()
        if normalized_confirm_name != company.name:
            raise BadRequestError(code="company_delete_confirm_mismatch", message="确认公司名称不匹配。")

        self._delete_company_cos_objects(company_id=company.id)
        self.company_repository.delete(company)
        self.db.commit()
