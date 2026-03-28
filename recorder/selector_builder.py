from __future__ import annotations

from typing import Any, Dict, Tuple


def _role_from_control_type(control_type: str) -> str:
    ct = (control_type or "").strip().casefold()
    if "button" in ct or "按钮" in control_type:
        return "button"
    if "edit" in ct or "textbox" in ct or "编辑" in control_type:
        return "textbox"
    if "listitem" in ct or "列表项" in control_type:
        return "listitem"
    if "menu" in ct or "菜单" in control_type:
        return "menuitem"
    return ct or "unknown"


def build_selector(target: Dict[str, Any]) -> Dict[str, Any]:
    """Build a minimal selector that can be used for future replay."""
    automation_id = str(target.get("automation_id") or "").strip()
    name = str(target.get("name") or "").strip()
    control_type = str(target.get("control_type") or "").strip()
    role = str(target.get("role") or "").strip() or _role_from_control_type(control_type)

    if automation_id:
        return {"automation_id": automation_id}
    # Fallback selector: less stable, but better than nothing.
    sel: Dict[str, Any] = {}
    if name:
        sel["name"] = name
    if role and role != "unknown":
        sel["role"] = role
    if not sel and control_type:
        sel["control_type"] = control_type
    return sel


def infer_role_and_dynamic_hint(target: Dict[str, Any]) -> Tuple[str, bool]:
    automation_id = str(target.get("automation_id") or "").strip()
    name = str(target.get("name") or "").strip()
    control_type = str(target.get("control_type") or "").strip()
    role = str(target.get("role") or "").strip() or _role_from_control_type(control_type)
    dynamic_hint = (not automation_id) and bool(name)
    return role, dynamic_hint

