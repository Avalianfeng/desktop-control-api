from __future__ import annotations

from typing import Literal

SemanticRole = Literal["action", "container", "text", "input", "unknown"]

# 引擎归一化后的 type -> 语义角色
ROLE_MAP: dict[str, SemanticRole] = {
    "button": "action",
    "menu_item": "action",
    "checkbox": "action",
    "radio": "action",
    "tab_item": "action",
    "list_item": "action",
    "input": "input",
    "text": "text",
    "window": "container",
    "container": "container",
    "menu": "container",
    "list": "container",
    "tab": "container",
    "group": "container",
    "pane": "container",
    "custom": "container",
    "unknown": "unknown",
}


def normalize_role(element_type: str) -> SemanticRole:
    """将 UIA 归一化类型映射为语义角色；未映射的默认为 container。"""
    t = (element_type or "").strip()
    if not t:
        return "container"
    return ROLE_MAP.get(t, "container")
