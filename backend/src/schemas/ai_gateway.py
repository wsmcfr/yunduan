"""AI 网关与模型配置相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models.enums import AIAuthMode, AIGatewayVendor, AIModelVendor, AIProtocolType
from src.schemas.common import ORMBaseModel


class AIModelProfileCreateRequest(BaseModel):
    """创建 AI 模型配置请求体。"""

    display_name: str = Field(min_length=1, max_length=128)
    upstream_vendor: AIModelVendor
    protocol_type: AIProtocolType
    auth_mode: AIAuthMode = AIAuthMode.AUTHORIZATION_BEARER
    base_url_override: str | None = Field(default=None, max_length=255)
    user_agent: str | None = Field(default=None, max_length=255)
    model_identifier: str = Field(min_length=1, max_length=255)
    supports_vision: bool = False
    supports_stream: bool = True
    is_enabled: bool = True
    note: str | None = None


class AIModelProfileUpdateRequest(BaseModel):
    """更新 AI 模型配置请求体。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    upstream_vendor: AIModelVendor | None = None
    protocol_type: AIProtocolType | None = None
    auth_mode: AIAuthMode | None = None
    base_url_override: str | None = Field(default=None, max_length=255)
    user_agent: str | None = Field(default=None, max_length=255)
    model_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    supports_vision: bool | None = None
    supports_stream: bool | None = None
    is_enabled: bool | None = None
    note: str | None = None


class AIModelProfileResponse(ORMBaseModel):
    """AI 模型配置响应体。"""

    id: int
    gateway_id: int
    display_name: str
    upstream_vendor: AIModelVendor
    protocol_type: AIProtocolType
    auth_mode: AIAuthMode
    base_url_override: str | None
    user_agent: str | None
    model_identifier: str
    supports_vision: bool
    supports_stream: bool
    is_enabled: bool
    note: str | None
    created_at: datetime
    updated_at: datetime


class AIGatewayCreateRequest(BaseModel):
    """创建 AI 网关请求体。"""

    name: str = Field(min_length=1, max_length=128)
    vendor: AIGatewayVendor
    official_url: str | None = Field(default=None, max_length=255)
    base_url: str = Field(min_length=1, max_length=255)
    note: str | None = None
    api_key: str = Field(min_length=1, max_length=512)
    is_enabled: bool = True
    is_custom: bool = False


class AIGatewayUpdateRequest(BaseModel):
    """更新 AI 网关请求体。

    约定：
    - `api_key` 为空或未传时，表示保留现有密钥。
    - 前端不会回填旧密钥，因此这里只允许覆盖，不允许读取原文。
    """

    name: str | None = Field(default=None, min_length=1, max_length=128)
    vendor: AIGatewayVendor | None = None
    official_url: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=255)
    note: str | None = None
    api_key: str | None = Field(default=None, max_length=512)
    is_enabled: bool | None = None
    is_custom: bool | None = None


class AIGatewayDiscoveryPreviewRequest(BaseModel):
    """新增/编辑网关弹窗内的临时模型探测请求体。"""

    vendor: AIGatewayVendor
    base_url: str = Field(min_length=1, max_length=255)
    api_key: str = Field(min_length=1, max_length=512)


class AIGatewayResponse(ORMBaseModel):
    """AI 网关基础响应体。"""

    id: int
    name: str
    vendor: AIGatewayVendor
    official_url: str | None
    base_url: str
    note: str | None
    is_enabled: bool
    is_custom: bool
    has_api_key: bool
    api_key_mask: str | None
    created_at: datetime
    updated_at: datetime


class AIGatewayDetailResponse(AIGatewayResponse):
    """AI 网关详情响应体，包含挂载的模型配置。"""

    models: list[AIModelProfileResponse]


class AIGatewayListResponse(BaseModel):
    """AI 网关列表响应体。"""

    items: list[AIGatewayDetailResponse]


class AIRuntimeModelOption(ORMBaseModel):
    """运行时可供业务侧选择的 AI 模型选项。"""

    id: int
    display_name: str
    upstream_vendor: AIModelVendor
    protocol_type: AIProtocolType
    user_agent: str | None
    model_identifier: str
    supports_vision: bool
    supports_stream: bool
    gateway_id: int
    gateway_name: str
    gateway_vendor: AIGatewayVendor
    base_url: str


class AIRuntimeModelOptionListResponse(BaseModel):
    """运行时模型选项列表响应体。"""

    items: list[AIRuntimeModelOption]


class AIDiscoveredModelCandidate(BaseModel):
    """通过网关自动探测到的模型候选项。"""

    model_identifier: str
    display_name: str
    upstream_vendor: AIModelVendor
    protocol_type: AIProtocolType
    auth_mode: AIAuthMode
    base_url: str
    user_agent: str | None
    supports_vision: bool
    supports_stream: bool
    source_label: str


class AIDiscoveredModelListResponse(BaseModel):
    """模型自动探测结果列表。"""

    items: list[AIDiscoveredModelCandidate]
