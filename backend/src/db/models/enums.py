"""数据库枚举定义。"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """系统用户角色枚举。"""

    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"


class DeviceType(str, Enum):
    """设备类型枚举。"""

    MP157 = "mp157"
    F4 = "f4"
    GATEWAY = "gateway"
    OTHER = "other"


class DeviceStatus(str, Enum):
    """设备在线状态枚举。"""

    ONLINE = "online"
    OFFLINE = "offline"
    FAULT = "fault"


class DetectionResult(str, Enum):
    """检测结果枚举。"""

    GOOD = "good"
    BAD = "bad"
    UNCERTAIN = "uncertain"


class ReviewStatus(str, Enum):
    """主记录审核状态枚举。"""

    PENDING = "pending"
    REVIEWED = "reviewed"
    AI_RESERVED = "ai_reserved"


class FileKind(str, Enum):
    """文件对象类型枚举。"""

    SOURCE = "source"
    ANNOTATED = "annotated"
    THUMBNAIL = "thumbnail"


class ReviewSource(str, Enum):
    """审核来源枚举。"""

    MANUAL = "manual"
    AI_RESERVED = "ai_reserved"


class StorageProvider(str, Enum):
    """对象存储提供商枚举。"""

    COS = "cos"


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """返回枚举成员的 value 列表，供 SQLAlchemy Enum 列统一复用。"""

    return [member.value for member in enum_cls]
