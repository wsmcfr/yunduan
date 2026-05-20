"""零件身份显示归一化工具。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PartDisplayIdentity:
    """保存某个零件编码对应的标准显示身份。"""

    name: str
    category: str | None


STANDARD_PART_DISPLAY_BY_CODE: dict[str, PartDisplayIdentity] = {
    "gasket": PartDisplayIdentity(name="波形垫圈", category="垫圈类"),
    "wave_washer": PartDisplayIdentity(name="波形垫圈", category="垫圈类"),
    "washer": PartDisplayIdentity(name="平垫圈", category="垫圈类"),
    "splitwasher": PartDisplayIdentity(name="弹性垫圈", category="垫圈类"),
}

LEGACY_WASHER_CATEGORY_ALIASES = {
    "垫圈",
    "垫片",
    "弹性垫圈",
    "washer-family",
    "washer_family",
}


def normalize_part_display_name(*, part_code: str, raw_name: str | None) -> str:
    """根据零件编码生成稳定中文显示名。

    参数:
        part_code: 模型或云端主数据中的零件编码，例如 gasket、washer。
        raw_name: 数据库中当前保存的显示名；未知编码会保留这个值。

    返回:
        已知编码返回业务标准名称；未知编码优先返回原名称，最后兜底为编码。
    """

    normalized_code = part_code.strip().lower()
    standard_identity = STANDARD_PART_DISPLAY_BY_CODE.get(normalized_code)
    if standard_identity is not None:
        return standard_identity.name

    normalized_name = (raw_name or "").strip()
    return normalized_name or part_code


def normalize_part_category(*, part_code: str, raw_category: str | None) -> str | None:
    """根据零件编码和历史分类文案生成稳定大类名称。

    参数:
        part_code: 模型或云端主数据中的零件编码。
        raw_category: 数据库中当前保存的分类文案。

    返回:
        已知垫圈类编码统一返回“垫圈类”；历史别名也归一到“垫圈类”。
    """

    normalized_code = part_code.strip().lower()
    standard_identity = STANDARD_PART_DISPLAY_BY_CODE.get(normalized_code)
    if standard_identity is not None:
        return standard_identity.category

    normalized_category = (raw_category or "").strip()
    if normalized_category in LEGACY_WASHER_CATEGORY_ALIASES:
        return "垫圈类"

    return normalized_category or None
