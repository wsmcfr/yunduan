"""初始化默认管理员脚本。"""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.config import get_settings
from src.core.security import hash_password
from src.db.models.company import Company
from src.db.models.enums import AdminApplicationStatus, UserRole
from src.db.models.user import User
from src.db.session import SessionLocal
from src.repositories.company_repository import CompanyRepository
from src.repositories.user_repository import UserRepository

SYSTEM_COMPANY_NAME = "系统默认公司"
SYSTEM_COMPANY_INVITE_CODE = "SYSDEFAULT01"


def seed_default_admin() -> None:
    """根据环境变量创建默认管理员账号。"""

    settings = get_settings()
    db = SessionLocal()
    try:
        # 部署环境如果没有显式提供默认管理员密码，就跳过自动播种，
        # 避免源码中的空值或占位值被误写成公网可预测账号。
        if not settings.default_admin_password.strip():
            print("未配置 DEFAULT_ADMIN_PASSWORD，跳过默认管理员初始化。")
            return

        company_repository = CompanyRepository(db)
        repository = UserRepository(db)
        system_company = company_repository.get_by_name(SYSTEM_COMPANY_NAME)
        if system_company is None:
            system_company = Company(
                name=SYSTEM_COMPANY_NAME,
                contact_name="平台默认管理员",
                note="系统保留公司，用于承接默认管理员与历史单租户数据。",
                invite_code=SYSTEM_COMPANY_INVITE_CODE,
                is_active=True,
                is_system_reserved=True,
            )
            company_repository.create(system_company)
            db.commit()
            db.refresh(system_company)

        existed_user = repository.get_by_username(settings.default_admin_username)
        if existed_user is not None:
            needs_update = False
            if existed_user.company_id != system_company.id:
                existed_user.company_id = system_company.id
                needs_update = True
            if not existed_user.is_default_admin:
                existed_user.is_default_admin = True
                needs_update = True
            if existed_user.admin_application_status != AdminApplicationStatus.APPROVED:
                existed_user.admin_application_status = AdminApplicationStatus.APPROVED
                needs_update = True
            if needs_update:
                repository.save(existed_user)
                db.commit()
            print(f"默认管理员已存在: {existed_user.username}")
            return

        # 首次启动时写入默认管理员，便于马上验证登录接口。
        admin_user = User(
            username=settings.default_admin_username,
            email=settings.default_admin_email,
            password_hash=hash_password(settings.default_admin_password),
            password_changed_at=datetime.now(timezone.utc),
            display_name=settings.default_admin_display_name,
            role=UserRole.ADMIN,
            company_id=system_company.id,
            is_default_admin=True,
            admin_application_status=AdminApplicationStatus.APPROVED,
            is_active=True,
            # 默认管理员需要具备完整系统运维能力，因此首次播种时直接开放 AI 权限。
            can_use_ai_analysis=True,
        )
        repository.create(admin_user)
        db.commit()
        print(f"默认管理员创建成功: {admin_user.username}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_admin()
