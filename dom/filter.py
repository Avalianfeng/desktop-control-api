from __future__ import annotations

from typing import Any, Mapping, Set, Union

from models.ui_dom import UIElement

# 与 engines/desktop_dom_engine._analyze_quality 中交互类型对齐，并含 list_item
ACTIONABLE_TYPES: Set[str] = {
    "button",
    "input",
    "menu_item",
    "list_item",
    "checkbox",
    "radio",
    "tab_item",
}

ElementLike = Union[UIElement, Mapping[str, Any]]


def _bounds_wh(el: ElementLike) -> tuple[int, int]:
    if isinstance(el, UIElement):
        b = el.bounds
        return (b.width, b.height)
    bounds = el.get("bounds") or {}
    w = bounds.get("width")
    h = bounds.get("height")
    if not isinstance(w, int) or not isinstance(h, int):
        return (0, 0)
    return (w, h)


def _enabled(el: ElementLike) -> bool:
    if isinstance(el, UIElement):
        return bool(el.enabled)
    v = el.get("enabled")
    return True if v is None else bool(v)


def _type(el: ElementLike) -> str:
    if isinstance(el, UIElement):
        return (el.type or "").strip()
    t = el.get("type")
    return (str(t) if t is not None else "").strip()


def is_visible(el: ElementLike) -> bool:
    """非零面积 bounds 视为可见（过滤 UIA 常见的 0x0）。"""
    w, h = _bounds_wh(el)
    return w > 0 and h > 0


def is_actionable(el: ElementLike) -> bool:
    """可操作：类型白名单 + 可见（正面积）+ 已启用。"""
    if _type(el) not in ACTIONABLE_TYPES:
        return False
    if not is_visible(el):
        return False
    if not _enabled(el):
        return False
    return True
