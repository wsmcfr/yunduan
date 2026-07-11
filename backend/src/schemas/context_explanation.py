"""MP157 上下文中文解释响应结构。"""

from __future__ import annotations

from pydantic import BaseModel


class ContextExplanationItem(BaseModel):
    """单个原始字段对应的一条中文解释。"""

    source_path: str
    label: str
    value_text: str
    explanation: str


class ContextExplanationGroup(BaseModel):
    """同一类上下文解释分组，例如视觉、传感器、判定或设备。"""

    key: str
    title: str
    summary: str
    items: list[ContextExplanationItem]


class ContextExplanationResponse(BaseModel):
    """一条检测记录的完整中文上下文解释。"""

    summary: str
    groups: list[ContextExplanationGroup]
