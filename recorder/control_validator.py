from __future__ import annotations

from typing import Any, Dict


def is_valid_control(control: Dict[str, Any]) -> bool:
    name = str(control.get("name") or "").strip()
    automation_id = str(control.get("automation_id") or "").strip()
    control_type = str(control.get("control_type") or "").strip()
    path = str(control.get("path") or "").strip()

    if name or automation_id or control_type:
        return True
    if not path or path == "Unknown":
        return False
    return False

