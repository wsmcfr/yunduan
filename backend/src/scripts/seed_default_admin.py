"""初始化默认管理员脚本。"""

from __future__ import annotations

from src.core.config import get_settings
from src.core.security import hash_password
from src.db.models.enums import UserRole
from src.db.models.user import User
from src.db.session import SessionLocal
from src.repositories.user_repository import UserRepository


def seed_default_admin() -> None:
    """根据环境变量创建默认管理员账号。"""

    settings = get_settings()
    db = SessionLocal()
    try:
        repository = UserRepository(db)
        existed_user = repository.get_by_username(settings.default_admin_username)
        if existed_user is not None:
            print(f"默认管理员已存在: {existed_user.username}")
            return

        # 首次启动时写入默认管理员，便于马上验证登录接口。
        admin_user = User(
            username=settings.default_admin_username,
            password_hash=hash_password(settings.default_admin_password),
            display_name=settings.default_admin_display_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        repository.create(admin_user)
        db.commit()
        print(f"默认管理员创建成功: {admin_user.username}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_admin()
