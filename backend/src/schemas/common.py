"""通用 Schema 定义。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMBaseModel(BaseModel):
    """所有响应模型共享的基础配置。"""

    model_config = ConfigDict(from_attributes=True)


class ApiMessageResponse(BaseModel):
    """用于返回简单提示信息的通用响应。"""

    message: str
