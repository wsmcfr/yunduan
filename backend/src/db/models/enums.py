"""数据库枚举定义。"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """系统用户角色枚举。"""

    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"


class AdminApplicationStatus(str, Enum):
    """新公司管理员申请状态枚举。

    `not_applicable` 表示该用户不是通过“申请开新公司”路径创建的，
    例如默认管理员、通过邀请码加入公司的普通成员等。
    """

    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


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


class AIGatewayVendor(str, Enum):
    """AI 网关供应商/中转品牌枚举。"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    ZHIPU = "zhipu"
    MOONSHOT = "moonshot"
    MINMAX = "minmax"
    DEEPSEEK = "deepseek"
    OPENCLAUDECODE = "openclaudecode"
    RELAY = "relay"
    CUSTOM = "custom"


class AIProtocolType(str, Enum):
    """后端适配外部模型时使用的协议类型枚举。"""

    ANTHROPIC_MESSAGES = "anthropic_messages"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI_RESPONSES = "openai_responses"
    GEMINI_GENERATE_CONTENT = "gemini_generate_content"


class AIAuthMode(str, Enum):
    """外部模型网关鉴权方式枚举。"""

    X_API_KEY = "x_api_key"
    AUTHORIZATION_BEARER = "authorization_bearer"
    BOTH = "both"
    QUERY_API_KEY = "query_api_key"


class AIModelVendor(str, Enum):
    """模型来源品牌枚举。

    这里描述的是最终运行的模型家族，而不是中转网关品牌。
    例如：`openclaudecode` 网关下的模型品牌仍然是 `claude`。
    """

    CODEX = "codex"
    CLAUDE = "claude"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GLM = "glm"
    KIMI = "kimi"
    MINMAX = "minmax"
    CUSTOM = "custom"


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """返回枚举成员的 value 列表，供 SQLAlchemy Enum 列统一复用。"""

    return [member.value for member in enum_cls]
