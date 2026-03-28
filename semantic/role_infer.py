from __future__ import annotations

from semantic.widget_types import WidgetRole


def infer_role(*, element_type: str, control_type: str, text: str, normalized: str) -> WidgetRole:
    et = (element_type or "").strip()
    ct = (control_type or "").strip()

    # Primary mapping: prefer normalized element_type from DesktopDOMEngine
    if et == "button":
        return "button"
    if et == "checkbox":
        return "checkbox"
    if et == "radio":
        return "radio"
    if et == "link":
        return "link"
    if et == "input":
        return "textbox"
    if et == "menu_item":
        return "menuitem"
    if et == "tab_item":
        return "tab"
    if et == "list_item":
        return "listitem"
    if et == "text":
        return "text"

    # Fallback: try to infer from raw control type where possible
    if "Hyperlink" in ct:
        return "link"
    if "Edit" in ct:
        return "textbox"
    if "Button" in ct:
        return "button"
    if "CheckBox" in ct:
        return "checkbox"
    if "RadioButton" in ct:
        return "radio"

    return "unknown"

