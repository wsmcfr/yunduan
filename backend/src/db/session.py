"""数据库会话管理。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_settings

# 引擎和会话工厂作为全局单例使用，避免重复创建连接池。
settings = get_settings()
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db_session() -> Session:
    """提供数据库会话依赖。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
